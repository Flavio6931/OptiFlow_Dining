"""Edición del plano: crear, mover, unificar y separar mesas."""
import json

from django.contrib.auth.models import User
from django.urls import reverse

from ..models import TableState
from .base import OperationalTestCase


class FloorPlanTests(OperationalTestCase):
    """Edición del plano: crear, mover, unificar y separar mesas."""

    def test_admin_can_create_move_and_unify_cad_tables(self):
        """Verifica la creación, reubicación y unificación dinámica de mesas CAD por Admin (Req 6)."""
        from ..layout import LAYOUT_PATH
        original_json = LAYOUT_PATH.read_text(encoding='utf-8')
        admin = User.objects.create_superuser(username='cad_admin', password='123', email='cad@test.com')
        self.client.force_login(admin)

        try:
            # 1. Crear nueva mesa 'mesa99' en zona A, nodo 1,4
            create_res = self.client.post(
                reverse('api_create_table'),
                data=json.dumps({
                    'code': 'mesa99',
                    'label': 'Mesa 99',
                    'seats': 6,
                    'zone': 'A',
                    'node': '1,4',
                }),
                content_type='application/json',
            )
            self.assertEqual(create_res.status_code, 201)
            self.assertTrue(TableState.objects.filter(code='mesa99').exists())

            # 2. Reubicar mesa99 a nodo 2,4
            move_res = self.client.post(
                reverse('api_move_table', args=['mesa99']),
                data=json.dumps({'node': '2,4', 'zone': 'B'}),
                content_type='application/json',
            )
            self.assertEqual(move_res.status_code, 200)
            self.assertEqual(move_res.json()['table']['node'], '2,4')

            # 3. Unificar mesa99 y mesa01 para grupo grande
            unify_res = self.client.post(
                reverse('api_unify_tables'),
                data=json.dumps({
                    'table_codes': ['mesa01', 'mesa99'],
                    'unified_code': 'mesa_vip_grupo',
                    'unified_label': 'Mesa VIP Consolidada',
                }),
                content_type='application/json',
            )
            self.assertEqual(unify_res.status_code, 200)
            data = unify_res.json()
            self.assertTrue(TableState.objects.filter(code='mesa_vip_grupo').exists())
            self.assertEqual(data['unified_table']['seats'], 10)  # 4 de mesa01 + 6 de mesa99

        finally:
            # Restaurar estado original de salon.json
            LAYOUT_PATH.write_text(original_json, encoding='utf-8')

    def test_waiter_cannot_modify_cad_layout(self):
        """Verifica que un mesero no tenga permisos para crear, mover o fusionar mesas CAD."""
        self.client.force_login(self.waiter)
        res_create = self.client.post(
            reverse('api_create_table'),
            data=json.dumps({'code': 'm_fake', 'label': 'Fake', 'node': '0,0'}),
            content_type='application/json',
        )
        self.assertEqual(res_create.status_code, 403)

        res_move = self.client.post(
            reverse('api_move_table', args=['mesa01']),
            data=json.dumps({'node': '0,0'}),
            content_type='application/json',
        )
        self.assertEqual(res_move.status_code, 403)

        res_unify = self.client.post(
            reverse('api_unify_tables'),
            data=json.dumps({'table_codes': ['mesa01', 'mesa02']}),
            content_type='application/json',
        )
        self.assertEqual(res_unify.status_code, 403)

    def test_cad_collision_detection_and_strict_bounds(self):
        """Verifica colisiones en cuadrícula, muro estricto de dimensiones y expansión explícita (Req CAD)."""
        from ..layout import LAYOUT_PATH, get_layout
        original_json = LAYOUT_PATH.read_text(encoding='utf-8')
        admin = User.objects.create_superuser(username='collision_admin', password='123', email='col@test.com')
        self.client.force_login(admin)

        try:
            # 1. Intentar crear mesa en posición ocupada por otra mesa (ej. '1,1' de mesa01) -> 400
            res_collision = self.client.post(
                reverse('api_create_table'),
                data=json.dumps({
                    'code': 'mesa_colision',
                    'label': 'Mesa Colisión',
                    'node': '1,1',
                    'seats': 4,
                    'zone': 'A',
                }),
                content_type='application/json',
            )
            self.assertEqual(res_collision.status_code, 400)
            self.assertIn('ya está ocupada', res_collision.json()['error'])

            # 2. Intentar crear mesa en posición de la cocina ('0,2') -> 400
            res_origin = self.client.post(
                reverse('api_create_table'),
                data=json.dumps({
                    'code': 'mesa_cocina',
                    'label': 'Mesa Cocina',
                    'node': '0,2',
                    'seats': 4,
                    'zone': 'A',
                }),
                content_type='application/json',
            )
            self.assertEqual(res_origin.status_code, 400)
            self.assertIn('ya está ocupada', res_origin.json()['error'])

            # 3. Muro estricto: crear mesa fuera de 5x5 ('5,6') debe ser rechazado con 400 (sin auto-expansión)
            res_out = self.client.post(
                reverse('api_create_table'),
                data=json.dumps({
                    'code': 'mesa_fuera',
                    'label': 'Mesa Fuera',
                    'node': '5,6',
                    'seats': 4,
                    'zone': 'C',
                }),
                content_type='application/json',
            )
            self.assertEqual(res_out.status_code, 400)
            self.assertIn('fuera de los límites', res_out.json()['error'])

            # 4. Ampliar dimensiones explícitamente a 8x7 permite crear mesa en (6,6) dentro de Zona C
            dim_res = self.client.post(
                reverse('api_update_layout_dimensions'),
                data=json.dumps({'columns': 8, 'rows': 7}),
                content_type='application/json',
            )
            self.assertEqual(dim_res.status_code, 200)
            updated_layout = get_layout()
            self.assertEqual(updated_layout['columns'], 8)
            self.assertEqual(updated_layout['rows'], 7)

            res_ok = self.client.post(
                reverse('api_create_table'),
                data=json.dumps({
                    'code': 'mesa_expandida',
                    'label': 'Mesa Expandida',
                    'node': '6,6',
                    'seats': 4,
                    'zone': 'C',
                }),
                content_type='application/json',
            )
            self.assertEqual(res_ok.status_code, 201)

        finally:
            LAYOUT_PATH.write_text(original_json, encoding='utf-8')

    def test_zone_change_relocates_physically_and_full_zone_alert(self):
        """Verifica que cambiar de zona reubique físicamente la mesa en el mapa y alerte si la zona está llena."""
        from ..layout import LAYOUT_PATH
        original_json = LAYOUT_PATH.read_text(encoding='utf-8')
        self.client.force_login(self.manager)

        try:
            # 1. Cambiar mesa01 (1,1 en Zona A) a Zona B enviando su nodo viejo ('1,1') debe moverla a col 2
            move_res = self.client.post(
                reverse('api_move_table', args=['mesa01']),
                data=json.dumps({'node': '1,1', 'zone': 'B'}),
                content_type='application/json',
            )
            self.assertEqual(move_res.status_code, 200)
            moved_table = move_res.json()['table']
            self.assertEqual(moved_table['zone'], 'B')
            self.assertEqual(int(moved_table['node'].split(',')[0]), 2)

            # 2. Llenar las 2 celdas libres restantes de Zona B (col 2 en plano 5x5 tiene 5 celdas: 2,1; 2,3; la recién ocupada y 2 más)
            for idx in range(2):
                add_res = self.client.post(
                    reverse('api_create_table'),
                    data=json.dumps({
                        'code': f'mesa_zb_{idx}',
                        'label': f'Mesa ZB {idx}',
                        'seats': 2,
                        'zone': 'B',
                        'node': 'auto',
                    }),
                    content_type='application/json',
                )
                self.assertEqual(add_res.status_code, 201)

            # 3. Intentar agregar o mover otra mesa a Zona B llena debe retornar alerta 400 clara
            full_res = self.client.post(
                reverse('api_move_table', args=['mesa05']),
                data=json.dumps({'node': 'auto', 'zone': 'B'}),
                content_type='application/json',
            )
            self.assertEqual(full_res.status_code, 400)
            self.assertIn('No hay espacio disponible para otra mesa en la Zona B', full_res.json()['error'])
        finally:
            LAYOUT_PATH.write_text(original_json, encoding='utf-8')

    def test_cad_separate_table_and_restoration(self):
        """Verifica la desunificación de mesas restaurando posiciones y estados originales (Req Desunificar)."""
        from ..layout import LAYOUT_PATH
        original_json = LAYOUT_PATH.read_text(encoding='utf-8')
        admin = User.objects.create_superuser(username='sep_admin', password='123', email='sep@test.com')
        self.client.force_login(admin)

        try:
            # 1. Unificar mesa01 y mesa02 en mesa_combo
            unify_res = self.client.post(
                reverse('api_unify_tables'),
                data=json.dumps({
                    'table_codes': ['mesa01', 'mesa02'],
                    'unified_code': 'mesa_combo',
                    'unified_label': 'Mesa Combo 1 y 2',
                }),
                content_type='application/json',
            )
            self.assertEqual(unify_res.status_code, 200)
            self.assertTrue(TableState.objects.filter(code='mesa_combo').exists())

            # 2. Separar mesa_combo
            sep_res = self.client.post(
                reverse('api_separate_table'),
                data=json.dumps({'code': 'mesa_combo'}),
                content_type='application/json',
            )
            self.assertEqual(sep_res.status_code, 200)
            self.assertIn('separada exitosamente', sep_res.json()['message'])

            # 3. Validar que mesa_combo ya no exista y que mesa01 y mesa02 vuelvan a estar en BD
            self.assertFalse(TableState.objects.filter(code='mesa_combo').exists())
            self.assertTrue(TableState.objects.filter(code='mesa01').exists())
            self.assertTrue(TableState.objects.filter(code='mesa02').exists())

        finally:
            LAYOUT_PATH.write_text(original_json, encoding='utf-8')
