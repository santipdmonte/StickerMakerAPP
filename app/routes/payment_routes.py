from flask import Blueprint, request, jsonify, session, url_for, redirect, current_app
import json
import uuid
import time
from decimal import Decimal
from datetime import datetime
from datetime import datetime, timedelta
from dynamodb_utils import (
    get_user,
    create_transaction,
    get_user_transactions,
    get_transaction_by_payment_id
)

from config import sdk

payment_bp = Blueprint('payment', __name__)


@payment_bp.route('/coin_payment_feedback')
def coin_payment_feedback():
    """
    Maneja el retorno del usuario desde Mercado Pago después de una compra de monedas.
    Ya no procesa el pago (eso lo hace el webhook), solo actualiza la sesión y
    redirige al usuario a la página principal.
    """
    current_app.logger.info("--- /coin_payment_feedback ---")

    payment_status = request.args.get('collection_status', '')
    payment_id = request.args.get('collection_id', '')
    external_reference = request.args.get('external_reference', '')
    
    current_app.logger.info(f"Callback de pago: Status={payment_status}, ID={payment_id}, ER={external_reference}")
    
    # Verificar que el usuario esté autenticado
    user_id = session.get('user_id')
    if not user_id:
        current_app.logger.warning("Usuario no autenticado en coin_payment_feedback. No se puede actualizar sesión.")
        return redirect(url_for('index'))
    
    # Solo mostramos feedback visual dependiendo del estado del pago
    if payment_status == 'approved':
        # Actualizar la sesión con las monedas actuales del usuario
        user = get_user(user_id)
        if user:
            session['coins'] = user.get('coins', 0)
            current_app.logger.info(f"Sesión actualizada para usuario {user_id}, monedas: {session['coins']}")
        else:
            current_app.logger.warning(f"No se pudo obtener usuario {user_id} para actualizar sesión")
        
        # Opcional: mensaje de éxito
        # session['payment_success_message'] = "¡Pago exitoso! Las monedas han sido acreditadas a tu cuenta."
    elif payment_status == 'rejected':
        current_app.logger.warning(f"Pago rechazado por Mercado Pago. ID: {payment_id}")
        # session['payment_error_message'] = "El pago fue rechazado. Por favor, intenta nuevamente."
    else:
        current_app.logger.info(f"Pago con estado {payment_status}. ID: {payment_id}")
        # session['payment_info_message'] = "El pago está siendo procesado. Las monedas serán acreditadas en breve."
    
    return redirect(url_for('index'))

@payment_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint para recibir notificaciones de Mercado Pago (IPN)
    
    Este endpoint maneja las notificaciones asíncronas de pagos:
    - Validación de seguridad
    - Procesamiento de pagos exitosos, fallidos o pendientes
    - Gestión de idempotencia para evitar procesar pagos duplicados
    """
    current_app.logger.info("--- WEBHOOK recibido de Mercado Pago ---")
    
    if not sdk:
        current_app.logger.error("Mercado Pago SDK no está configurado para recibir notificaciones.")
        return '', 200  # Devolver 200 para no recibir reenvíos, aunque hayamos fallado
    
    try:
        # Obtener los datos del webhook
        data = request.json
        current_app.logger.info(f"Datos de webhook recibidos: {data}")
        
        # Verificamos el tipo de notificación
        if 'resource' in data and 'topic' in data:
            # Formato de webhook clásico de Mercado Pago
            resource = data.get('resource')
            topic = data.get('topic')
            
            current_app.logger.info(f"Notificación de tipo {topic}, recurso: {resource}")
            
            if topic == 'payment':
                # Extraer el ID del pago de la URL del recurso
                payment_id = resource.split('/')[-1]
                current_app.logger.info(f"Procesando notificación para pago ID: {payment_id}")
                
                # Obtener detalles del pago usando el SDK
                payment_info = sdk.payment().get(payment_id)
                
                if payment_info["status"] == 200:
                    payment_data = payment_info["response"]
                    process_payment_webhook(payment_data)
                else:
                    current_app.logger.error(f"Error obteniendo información del pago {payment_id}: {payment_info}")
            elif topic == 'merchant_order':
                # Procesar notificación de merchant_order si es necesario
                current_app.logger.info(f"Notificación de merchant_order recibida, no se requiere acción en este momento")
            else:
                current_app.logger.warning(f"Tipo de topic no manejado: {topic}")
        else:
            # Podría ser otro formato de notificación
            current_app.logger.warning(f"Formato de webhook no reconocido: {data}")
    except Exception as e:
        current_app.logger.error(f"Error procesando webhook: {str(e)}", exc_info=True)
    
    # Siempre devolvemos 200 OK para evitar reenvíos automáticos
    return '', 200

def process_payment_webhook(payment_data):
    """
    Procesa los datos de un pago notificado por webhook
    
    Esta función extrae la información relevante del pago y actualiza
    la base de datos para reflejar el estado del pago.
    
    Args:
        payment_data (dict): Datos del pago provenientes de Mercado Pago
    """
    try:
        payment_id = payment_data.get('id')
        status = payment_data.get('status')
        external_reference = payment_data.get('external_reference')
        
        current_app.logger.info(f"Procesando pago ID: {payment_id}, Status: {status}, ER: {external_reference}")
        
        if not external_reference:
            current_app.logger.warning(f"Pago {payment_id} sin external_reference, no se puede procesar")
            return
        
        # Primero verificamos si esta transacción ya fue procesada (verificación explícita)
        existing_transaction = get_transaction_by_payment_id(payment_id)
        if existing_transaction:
            current_app.logger.info(f"Pago {payment_id} ya fue procesado anteriormente en transacción {existing_transaction.get('transaction_id')}. No se realiza acción adicional.")
            return
        
        # Solo procesamos pagos aprobados
        if status == 'approved':
            # Parsear external_reference: COINPKG_{user_id}_{package_id}_{coins}_{timestamp}
            ref_parts = external_reference.split('_')
            
            if len(ref_parts) == 5 and ref_parts[0] == 'COINPKG':
                user_id = ref_parts[1]
                package_id = ref_parts[2]
                coins_to_add = int(ref_parts[3])
                
                # Verificar si el usuario existe
                user = get_user(user_id)
                if not user:
                    current_app.logger.error(f"Usuario {user_id} no encontrado, no se pueden asignar monedas")
                    return
                
                # Crear la transacción (con idempotencia basada en payment_id)
                transaction = create_transaction(
                    user_id=user_id,
                    coins_amount=coins_to_add,
                    transaction_type='coin_purchase_mp',
                    details={
                        'payment_id': payment_id,
                        'payment_status': status,
                        'external_reference': external_reference,
                        'package_id': package_id,
                        'source': 'webhook'
                    },
                    payment_id=payment_id  # Usar payment_id para idempotencia
                )
                
                # Verificar si la transacción fue realmente creada o si ya existía
                is_new_transaction = not transaction.get('is_existing', False)
                
                if is_new_transaction:
                    current_app.logger.info(f"Transacción {transaction['transaction_id']} creada para usuario {user_id}, {coins_to_add} monedas añadidas")
                else:
                    current_app.logger.info(f"Transacción con payment_id {payment_id} ya existía, no se duplicó")
            else:
                current_app.logger.error(f"Formato de external_reference inválido: {external_reference}")
        else:
            current_app.logger.info(f"Pago con status {status}, no se requiere acción (sólo procesamos 'payment_bproved')")
            
    except Exception as e:
        current_app.logger.error(f"Error procesando datos de pago en webhook: {str(e)}", exc_info=True)

def reconcile_payments():
    """
    Función de reconciliación para revisar pagos que podrían no haberse registrado.
    
    Esta función consulta a Mercado Pago por pagos aprobados recientes y verifica
    que todas las transacciones correspondientes estén registradas en la base de datos.
    Se usa para garantizar que no se pierdan pagos debido a fallos en webhooks.
    """
    current_app.logger.info("Iniciando proceso de reconciliación de pagos...")
    
    if not sdk:
        current_app.logger.error("Mercado Pago SDK no está configurado para la reconciliación de pagos")
        return 0
    
    try:
        # Definir el rango de fechas para buscar (últimas 48 horas)
        yesterday = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        
        current_app.logger.info(f"Buscando pagos entre {yesterday} y {today}")
        
        # Buscar pagos recientes en Mercado Pago
        search_params = {
            "begin_date": yesterday + "T00:00:00.000-03:00",
            "end_date": today + "T23:59:59.999-03:00",
            "status": "approved"
        }
        
        payment_search_result = sdk.payment().search(search_params)
        
        if payment_search_result["status"] != 200:
            current_app.logger.error(f"Error buscando pagos en Mercado Pago: {payment_search_result}")
            return 0
        
        payments = payment_search_result["response"].get("results", [])
        current_app.logger.info(f"Se encontraron {len(payments)} pagos aprobados en Mercado Pago")
        
        reconciled_count = 0
        skipped_count = 0
        
        # Procesar cada pago encontrado
        for payment in payments:
            payment_id = payment.get("id")
            external_reference = payment.get("external_reference", "")
            
            # Solo procesamos pagos relacionados con nuestro sistema
            if external_reference and external_reference.startswith("COINPKG_"):
                current_app.logger.info(f"Verificando pago {payment_id} con referencia {external_reference}...")
                
                # Verificar si ya hemos procesado este pago
                existing_transaction = get_transaction_by_payment_id(payment_id)
                
                if existing_transaction:
                    current_app.logger.info(f"Pago {payment_id} ya está registrado en la transacción {existing_transaction.get('transaction_id')}")
                    skipped_count += 1
                else:
                    current_app.logger.info(f"Pago {payment_id} no registrado, procesando...")
                    # Procesar el pago como si fuera una notificación de webhook
                    process_payment_webhook(payment)
                    reconciled_count += 1
            else:
                current_app.logger.info(f"Pago {payment_id} no está relacionado con monedas (ER: {external_reference})")
        
        current_app.logger.info(f"Reconciliación completada. {reconciled_count} pagos procesados, {skipped_count} omitidos por ya existir.")
        return reconciled_count
        
    except Exception as e:
        current_app.logger.error(f"Error en el proceso de reconciliación: {str(e)}", exc_info=True)
        return 0

@payment_bp.route('/admin/reconcile-payments', methods=['GET'])
def admin_reconcile_payments():
    """
    Ruta administrativa para ejecutar manualmente el proceso de reconciliación
    Esta ruta ejecuta el proceso y devuelve un informe de los resultados
    """
    # TODO: Añadir autenticación/autorización para esta ruta
    
    try:
        result = reconcile_payments()
        
        # Preparar respuesta detallada
        return jsonify({
            "success": True,
            "reconciled_payments": result,
            "message": f"Proceso de reconciliación completado. {result} pagos procesados."
        })
    except Exception as e:
        current_app.logger.error(f"Error al ejecutar reconciliación desde endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Error al ejecutar el proceso de reconciliación"
        }), 500