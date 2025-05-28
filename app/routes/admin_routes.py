from flask import Blueprint, request, session, redirect, url_for, render_template, abort, flash
from utils.dynamodb_utils import get_user, create_admin_request, get_admin_request, approve_admin_request, update_user_role
from functools import wraps
from config import ADMIN_REQUEST_PASSWORD
from utils.utils import send_admin_request_email, format_timestamp
from utils.admin_kpi_utils import (
    get_total_users, get_new_users, get_active_users, get_total_transactions,
    get_total_revenue, get_average_order_value, get_recent_admin_requests
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Decorador para requerir rol de administrador
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('index'))
        user = get_user(user_id)
        if not user or user.get('role') != 'admin':
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@admin_required
def admin_root():
    # Check if user is admin
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    user = get_user(user_id)
    if not user or user.get('role') != 'admin':
        return redirect(url_for('admin.request_admin'))

    # KPIs
    total_users = get_total_users()
    new_users = get_new_users(7)
    active_users = get_active_users(1)
    total_transactions = get_total_transactions()
    total_revenue = get_total_revenue()
    avg_order_value = get_average_order_value()
    recent_admin_requests = get_recent_admin_requests(5)

    # Formatear fechas
    for req in recent_admin_requests:
        req['created_at_str'] = format_timestamp(req.get('created_at'))

    return render_template(
        'admin/admin.html',
        total_users=total_users,
        new_users=new_users,
        active_users=active_users,
        total_transactions=total_transactions,
        total_revenue=total_revenue,
        avg_order_value=avg_order_value,
        recent_admin_requests=recent_admin_requests
    )

@admin_bp.route('/request', methods=['GET', 'POST'])
def request_admin():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))
    user = get_user(user_id)
    if not user:
        return redirect(url_for('index'))
    if user.get('role') == 'admin':
        return redirect(url_for('admin.admin_dashboard'))

    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password != ADMIN_REQUEST_PASSWORD:
            error = "Contraseña incorrecta."
        else:
            # Generar token y guardar solicitud
            token = create_admin_request(user_id, user['email'])
            # Enviar mail al superadmin usando la función utilitaria
            validation_url = url_for('admin.validate_admin', token=token, _external=True)
            send_admin_request_email(user['email'], validation_url)
            flash("Solicitud enviada. Un administrador revisará tu petición.", "success")
            return redirect(url_for('index'))

    return render_template('admin/request_admin.html', error=error)

@admin_bp.route('/validate/<token>', methods=['GET', 'POST'])
def validate_admin(token):
    req = get_admin_request(token)
    if not req or req['status'] != 'pending':
        return "Solicitud inválida o ya procesada.", 400
    if request.method == 'POST':
        # Aprobar solicitud
        approve_admin_request(token)
        update_user_role(req['user_id'], 'admin')
        flash("Usuario promovido a admin.", "success")
        return redirect(url_for('admin.admin_dashboard'))
    return render_template('admin/validate_admin.html', req=req)