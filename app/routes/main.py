from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from ..models import Medicamento, Usuario, Rede, db
from ..extensions import csrf
from datetime import datetime, date, timedelta
import json, io

main_bp = Blueprint('main', __name__)

def get_usuario_atual():
    user_id = session.get('user_id')
    if not user_id: return None
    return Usuario.query.get(user_id)

@main_bp.route('/')
def dashboard():
    u = get_usuario_atual()
    if not u: return redirect(url_for('auth.login'))
    
    # Lógica de dashboard extraída do app.py original...
    # (Simplificado para este exemplo, mas contendo o essencial)
    meds = Medicamento.query.filter_by(rede_id=u.rede_id).all()
    stats = {
        'total': len(meds),
        'vencidos': len([m for m in meds if m.status == 'vencido']),
        'alerta_30': len([m for m in meds if m.status == 'alerta_30']),
        'alerta_60': len([m for m in meds if m.status == 'alerta_60']),
        'ok': len([m for m in meds if m.status == 'ok']),
    }
    
    return render_template('index.html', usuario=u, medicamentos=meds, stats=stats, hoje=date.today())

@main_bp.route('/medicamentos/bulk-excluir', methods=['POST'])
def bulk_excluir():
    # Lógica que acabamos de criar...
    ids = request.json.get('ids', [])
    u = get_usuario_atual()
    Medicamento.query.filter(Medicamento.id.in_(ids), Medicamento.rede_id == u.rede_id).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True})
