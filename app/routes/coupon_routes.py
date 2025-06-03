from flask import Blueprint, request, jsonify, render_template
from services.coupon_services import (
    create_coupon, get_coupon_by_code, list_coupons, redeem_coupon, set_coupon_active, delete_coupon
)
from routes.admin_routes import admin_required

coupon_bp = Blueprint('coupon', __name__)

# Crear cupón
@coupon_bp.route('/coupons', methods=['POST'])
@admin_required
def create_coupon_route():
    data = request.get_json()

    try:
        coupon = create_coupon(data)
        return jsonify(coupon), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Listar cupones
@coupon_bp.route('/coupons', methods=['GET'])
@admin_required
def list_coupons_route():
    filters = request.args.to_dict()
    try:
        coupons = list_coupons(filters if filters else None)
        return jsonify(coupons)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Obtener cupón por código
@coupon_bp.route('/coupons/<coupon_code>', methods=['GET'])
def get_coupon_by_code_route(coupon_code):
    coupon = get_coupon_by_code(coupon_code)
    if not coupon:
        return jsonify({'error': 'Cupón no encontrado'}), 404
    return jsonify(coupon)

# Redimir cupón
@coupon_bp.route('/coupons/redeem', methods=['POST'])
def redeem_coupon_route():
    data = request.json
    user_id = data.get('user_id')
    coupon_code = data.get('coupon_code')
    if not user_id or not coupon_code:
        return jsonify({'error': 'Faltan parámetros'}), 400
    result = redeem_coupon(user_id, coupon_code)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)

# Activar/desactivar cupón
@coupon_bp.route('/coupons/<coupon_code>/activate', methods=['PATCH'])
@admin_required
def activate_coupon_route(coupon_code):
    data = request.json
    is_active = data.get('is_active')
    if is_active is None:
        return jsonify({'error': 'Falta is_active'}), 400
    result = set_coupon_active(coupon_code, is_active)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)

# Eliminar cupón
@coupon_bp.route('/coupons/<coupon_code>', methods=['DELETE'])
@admin_required
def delete_coupon_route(coupon_code):
    result = delete_coupon(coupon_code)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)

# Página de administración de cupones
@coupon_bp.route('/admin/coupons', methods=['GET'])
@admin_required
def coupons_admin_page():
    return render_template('admin/coupons_admin.html')
