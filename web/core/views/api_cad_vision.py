"""APIs REST de gestión CAD del plano de mesas y análisis computacional OpenCV + AWS S3."""
import base64
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

import core.views as views_pkg

from ..layout import add_table, move_table, separate_table, unify_tables, update_dimensions
from ..models import TableState, VisionAnalysis, Zone
from ..serializers import TableStateUpdateSerializer, VisionUploadSerializer
from .helpers import drf_role_required

logger = logging.getLogger(__name__)


@api_view(['POST'])
@drf_role_required('capitan', 'gerente')
def api_update_table(request, code):
    """Actualiza el estado operativo en vivo de una mesa (disponible, activa u ocupada)."""
    table = get_object_or_404(TableState, code=code)
    serializer = TableStateUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        first_err = next(iter(serializer.errors.values()))
        err_msg = first_err[0] if isinstance(first_err, list) else str(first_err)
        return Response(
            {'error': err_msg, 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    state_val = serializer.validated_data['state']
    table.state = state_val
    table.save(update_fields=['state', 'updated_at'])
    return Response(
        {'success': True, 'code': table.code, 'state': state_val},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_create_table(request):
    """Crea una nueva mesa en el plano CAD validando muros de dimensión y disponibilidad en la zona."""
    code = str(request.data.get('code', '')).strip().lower()
    label = str(request.data.get('label', '')).strip()
    seats = request.data.get('seats', 4)
    zone = str(request.data.get('zone', 'A')).strip().upper() or 'A'
    node = str(request.data.get('node', '')).strip() or 'auto'

    if not code:
        return Response({'error': 'El código de la mesa es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
    if not label:
        label = f"Mesa {code.replace('mesa', '').zfill(2)}"

    try:
        seats_num = int(seats)
        if seats_num <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return Response(
            {'error': 'La capacidad de comensales debe ser un número entero positivo.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        new_table = add_table(code=code, label=label, seats=seats_num, zone=zone, node=node)
        return Response({
            'success': True,
            'table': new_table,
            'message': (
                f"Mesa '{new_table['label']}' creada en posición ({new_table['node']}) · Zona {new_table['zone']}."
            ),
        }, status=status.HTTP_201_CREATED)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_move_table(request, code):
    """Reubica las coordenadas y/o sector zonal de una mesa respetando límites y capacidad de zona."""
    new_node = str(request.data.get('node', '')).strip() or None
    new_zone = str(request.data.get('zone', '')).strip().upper() or None

    if not new_node and not new_zone:
        return Response(
            {'error': 'Se requiere al menos el nuevo nodo (X,Y) o la nueva zona de reubicación.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        updated = move_table(code=code, new_node=new_node, new_zone=new_zone)
        return Response({
            'success': True,
            'table': updated,
            'message': (
                f"Mesa '{updated['label']}' reubicada exitosamente a posición ({updated['node']}) · Zona {updated['zone']}."
            ),
        }, status=status.HTTP_200_OK)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_unify_tables(request):
    """Fusiona dos o más mesas contiguas para grupos grandes preservando posiciones originales."""
    table_codes = request.data.get('table_codes', [])
    unified_code = str(request.data.get('unified_code', '')).strip().lower()
    unified_label = str(request.data.get('unified_label', '')).strip()

    if not isinstance(table_codes, list) or len(table_codes) < 2:
        return Response(
            {'error': 'Debes seleccionar al menos 2 mesas para fusionar.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not unified_code:
        unified_code = f"mesa_{'_'.join(c.replace('mesa', '') for c in table_codes)}"
    if not unified_label:
        unified_label = f"Mesa {'+'.join(c.replace('mesa', '') for c in table_codes)} (Grupo)"

    try:
        unified = unify_tables(
            table_codes=table_codes,
            unified_code=unified_code,
            unified_label=unified_label,
        )
        return Response({
            'success': True,
            'unified_table': unified,
            'message': f"Mesas fusionadas exitosamente en '{unified['label']}' (Capacidad: {unified['seats']} personas).",
        }, status=status.HTTP_200_OK)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_separate_table(request):
    """Desunifica una mesa compuesta restaurando las mesas originales en el plano y base de datos."""
    code = str(request.data.get('code', '')).strip().lower()
    if not code:
        return Response({'error': 'El código de la mesa a separar es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        restored = separate_table(unified_code=code)
        return Response({
            'success': True,
            'restored_tables': restored,
            'message': f"Mesa '{code}' separada exitosamente. Se restauraron {len(restored)} mesas originales.",
        }, status=status.HTTP_200_OK)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('admin', 'gerente')
def api_update_layout_dimensions(request):
    """Actualiza las dimensiones (columnas X y filas Y) de la cuadrícula CAD del salón."""
    try:
        columns = int(request.data.get('columns', 0))
        rows = int(request.data.get('rows', 0))
    except (ValueError, TypeError):
        return Response(
            {'error': 'Las columnas y filas deben ser números enteros.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        dims = update_dimensions(columns=columns, rows=rows)
        return Response({
            'success': True,
            'dimensions': dims,
            'message': f"Dimensiones del salón actualizadas a {dims['columns']}x{dims['rows']}.",
        }, status=status.HTTP_200_OK)
    except ValueError as val_err:
        return Response({'error': str(val_err)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@drf_role_required('gerente')
@parser_classes([MultiPartParser, FormParser])
def api_vision(request):
    """Procesa fotografías del salón con OpenCV, propaga densidad a zonas y archiva en S3."""
    serializer = VisionUploadSerializer(data=request.FILES)
    if not serializer.is_valid():
        first_err = next(iter(serializer.errors.values()))
        err_msg = first_err[0] if isinstance(first_err, list) else str(first_err)
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if 'supera' in err_msg
            else status.HTTP_400_BAD_REQUEST
        )
        return Response({'error': err_msg}, status=status_code)

    uploaded = serializer.validated_data['file']
    raw = uploaded.read()
    if len(raw) > 5 * 1024 * 1024:
        return Response(
            {'error': 'Archivo demasiado grande.'},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    try:
        http_code, result = views_pkg.analyze_image(uploaded.name, raw, uploaded.content_type)
    except views_pkg.ServiceUnavailable as exc:
        return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if http_code != 200:
        return Response(
            {'error': result.get('detail', 'Imagen inválida')},
            status=http_code,
        )

    try:
        s3_key = views_pkg.optional_upload_s3(raw, uploaded.name, uploaded.content_type)
    except Exception as s3_err:
        logger.warning('Fallo al subir evidencia a S3 (%s)', s3_err)
        s3_key = ''
        result['aws_warning'] = 'No se pudo guardar la imagen en AWS S3. Revisa el bucket y los permisos IAM.'

    updated_zones_info = []
    zone_counts = result.get('zone_counts', {})
    for code, count in zone_counts.items():
        zone_obj = Zone.objects.filter(code=code.upper()).first()
        if zone_obj:
            if count >= 3:
                zone_obj.level = 'critica'
                zone_obj.dwell_minutes = max(zone_obj.dwell_minutes, 4.5)
            elif count >= 1:
                if zone_obj.level != 'critica':
                    zone_obj.level = 'moderada'
                    zone_obj.dwell_minutes = max(zone_obj.dwell_minutes, 2.5)
            else:
                if zone_obj.dwell_minutes <= 2.0:
                    zone_obj.level = 'normal'
            zone_obj.save(update_fields=['level', 'dwell_minutes', 'updated_at'])
            updated_zones_info.append({
                'code': zone_obj.code,
                'level': zone_obj.level,
                'level_display': zone_obj.get_level_display(),
                'dwell_minutes': round(zone_obj.dwell_minutes, 1),
                'people_count': count,
            })

    VisionAnalysis.objects.create(
        user=request.user,
        filename=uploaded.name[:180],
        people_count=result['people_count'],
        zone_counts=zone_counts,
        s3_key=s3_key,
    )
    result['aws_saved'] = bool(s3_key)
    result['s3_key'] = s3_key
    if s3_key:
        result['s3_status'] = f'Evidencia archivada en AWS S3 ({s3_key})'
    elif result.get('aws_warning'):
        result['s3_status'] = 'Almacenamiento local (falló conexión a AWS S3)'
    else:
        result['s3_status'] = 'Almacenamiento local (AWS S3 no configurado)'

    annotated_b64 = result.get('annotated_image', '')
    if annotated_b64 and ',' in annotated_b64:
        try:
            b64_part = annotated_b64.split(',', 1)[1]
            if len(b64_part) > 40:
                b64_part += '=' * (-len(b64_part) % 4)
                img_bytes = base64.b64decode(b64_part)
                target_path = settings.BASE_DIR / 'static' / 'img' / 'latest_vision_capture.jpg'
                target_path.write_bytes(img_bytes)
        except Exception as write_err:
            logger.debug('No se pudo escribir latest_vision_capture.jpg: %s', write_err)

    result['updated_zones'] = updated_zones_info
    result['sync_notice'] = (
        'Saturación de zonas sincronizada con OpenCV. El ruteo Dijkstra esquivará '
        'automáticamente los pasillos con mayor aglomeración.'
    )
    return Response(result, status=status.HTTP_200_OK)


@login_required
def api_latest_vision(request):
    """Retorna metadatos y ruta de la última captura procesada por OpenCV para el modal de alertas."""
    recent_vision = VisionAnalysis.objects.order_by('-created_at').first()
    return JsonResponse({
        'image_url': '/static/img/latest_vision_capture.jpg',
        'people_count': recent_vision.people_count if recent_vision else 1,
        'zone_counts': recent_vision.zone_counts if recent_vision else {'A': 0, 'B': 1, 'C': 0},
        'filename': recent_vision.filename if recent_vision else 'captura_salon.jpg',
        'created_at': recent_vision.created_at.strftime('%d/%m/%Y %H:%M') if recent_vision else '',
    })

