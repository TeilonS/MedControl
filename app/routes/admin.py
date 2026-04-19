from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from ..models import Usuario, Rede, db
from datetime import datetime, date, timedelta

admin_bp = Blueprint('admin', __name__)

def is_admin():
    return session.get('perfil') == 'superadmin'

@admin_bp.before_request
def check_admin():
    if not is_admin():
        abort(403)

@admin_bp.route('/dashboard')
def dashboard():
    redes = Rede.query.all()
    return render_template('admin/dashboard.html', redes=redes)

@admin_bp.route('/rede/<int:id>')
def rede_detalhe(id):
    rede = Rede.query.get_or_404(id)
    return render_template('admin/rede_detalhe.html', rede=rede)
