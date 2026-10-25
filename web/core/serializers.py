"""Serializadores de Django REST Framework para validación y transformación de datos."""
from rest_framework import serializers

from .layout import get_layout
from .models import Profile, RouteConsultation, TableState, VisionAnalysis, Zone


class RouteRequestSerializer(serializers.Serializer):
    """Serializador para validar los parámetros de cálculo de ruta."""
    origin = serializers.CharField(max_length=20, default='cocina')
    destination = serializers.CharField(max_length=20, default='mesa08')
    task_type = serializers.ChoiceField(choices=['entrega', 'retiro'], default='entrega')
    avoid_congestion = serializers.BooleanField(default=False)

    def validate(self, attrs):
        """Valida que origen y destino existan en el layout del restaurante."""
        layout = get_layout()
        origins = {x['id'] for x in layout['origins']}
        tables = {x['id'] for x in layout['tables']}

        origin = attrs.get('origin', 'cocina')
        destination = attrs.get('destination', 'mesa08')

        if origin not in origins:
            raise serializers.ValidationError({'origin': 'El punto de origen no es válido.'})
        if destination not in tables:
            raise serializers.ValidationError({'destination': 'La mesa de destino no es válida.'})
        return attrs


class RouteConsultationSerializer(serializers.ModelSerializer):
    """Serializador del modelo de auditoría de consultas de ruta."""
    class Meta:
        model = RouteConsultation
        fields = [
            'id',
            'user',
            'origin',
            'destination',
            'task_type',
            'path',
            'distance',
            'recalculated',
            'congested',
            'completed',
            'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']


class ZoneSerializer(serializers.ModelSerializer):
    """Serializador para lectura del estado de zonas de saturación."""
    class Meta:
        model = Zone
        fields = ['id', 'code', 'level', 'dwell_minutes', 'updated_at']


class ZoneUpdateSerializer(serializers.Serializer):
    """Serializador para validación de actualización de nivel y permanencia en zona."""
    level = serializers.ChoiceField(choices=['normal', 'moderada', 'critica'])
    dwell_minutes = serializers.FloatField(min_value=0.0, max_value=240.0, default=0.0)


class TableStateSerializer(serializers.ModelSerializer):
    """Serializador para lectura del estado operativo de mesas."""
    class Meta:
        model = TableState
        fields = ['id', 'code', 'state', 'assigned_to', 'updated_at']


class TableStateUpdateSerializer(serializers.Serializer):
    """Serializador para actualización de estado operativo de mesa."""
    state = serializers.ChoiceField(choices=['disponible', 'activa', 'ocupada'])


class VisionUploadSerializer(serializers.Serializer):
    """Serializador para carga de archivos de imagen hacia el módulo OpenCV."""
    file = serializers.FileField()

    def validate_file(self, value):
        """Verifica formato de imagen MIME y tamaño máximo de 5 MB."""
        valid_types = {'image/jpeg', 'image/png', 'image/webp'}
        if value.content_type not in valid_types:
            raise serializers.ValidationError('Solo se admiten formatos JPEG, PNG o WebP.')
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('El archivo supera el tamaño máximo permitido de 5 MB.')
        return value


class VisionAnalysisSerializer(serializers.ModelSerializer):
    """Serializador del modelo de análisis fotográfico de ocupación."""
    class Meta:
        model = VisionAnalysis
        fields = [
            'id',
            'user',
            'filename',
            'people_count',
            'zone_counts',
            's3_key',
            'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']
