from flask import Blueprint, request, jsonify
from ..models import Medicamento, Rede, db, Usuario
from ..extensions import csrf
from functools import wraps
from datetime import date as _date

api_bp = Blueprint('api', __name__)

def api_key_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = (request.headers.get("X-API-Key") or
               request.args.get("api_key") or "").strip()
        if not key:
            return jsonify({"success": False, "error": "API Key nao informada. Use o header X-API-Key."}), 401
        rede = Rede.query.filter_by(token_api=key).first()
        if not rede:
            return jsonify({"success": False, "error": "API Key invalida."}), 403
        if not rede.assinatura_ativa:
            return jsonify({"success": False, "error": "Assinatura inativa. Renove o plano."}), 403
        request.rede_autenticada = rede
        return f(*args, **kwargs)
    return decorated

@api_bp.route('/v1/medicamentos', methods=['GET', 'POST'])
@csrf.exempt
@api_key_required
def api_listar():
    rede = request.rede_autenticada
    if request.method == 'POST':
        dados = request.get_json(silent=True) or {}
        erros = [c for c in ('nome', 'lote', 'data_validade', 'quantidade') if not dados.get(c)]
        if erros:
            return jsonify({'success': False, 'error': f'Campos obrigatorios: {", ".join(erros)}'}), 400
        try:
            validade = _date.fromisoformat(dados['data_validade'])
        except ValueError:
            return jsonify({'success': False, 'error': 'data_validade invalida. Use YYYY-MM-DD.'}), 400
        filial_id = dados.get('filial_id')
        if filial_id:
            filial = Usuario.query.filter_by(id=filial_id, rede_id=rede.id, perfil='filial').first()
            if not filial:
                return jsonify({'success': False, 'error': 'filial_id nao encontrada nesta rede.'}), 400
        med = Medicamento(
            nome           = str(dados['nome'])[:200],
            lote           = str(dados['lote'])[:50],
            data_validade  = validade,
            quantidade     = int(dados['quantidade']),
            codigo_barras  = str(dados.get('codigo_barras') or '')[:50] or None,
            fabricante     = str(dados.get('fabricante') or '')[:150] or None,
            preco_unitario = float(dados.get('preco_unitario') or 0),
            origem_cadastro= str(dados.get('origem', 'api'))[:50],
            codigo_externo = str(dados.get('codigo_externo') or '')[:100] or None,
            rede_id        = rede.id,
            filial_id      = filial_id,
        )
        db.session.add(med)
        db.session.commit()
        return jsonify({'success': True, 'id': med.id, 'message': 'Medicamento cadastrado com sucesso.'}), 201
    
    status    = request.args.get('status')
    filial_id = request.args.get('filial_id')
    query     = Medicamento.query.filter_by(rede_id=rede.id)
    if filial_id:
        query = query.filter_by(filial_id=filial_id)
    meds = query.all()
    if status:
        meds = [m for m in meds if m.status == status]
    return jsonify({'success': True, 'total': len(meds), 'data': [m.to_dict() for m in meds]})

@api_bp.route('/v1/medicamentos/<int:med_id>', methods=['PUT', 'DELETE'])
@csrf.exempt
@api_key_required
def api_medicamento_detalhe(med_id):
    rede = request.rede_autenticada
    med  = Medicamento.query.filter_by(id=med_id, rede_id=rede.id).first()
    if not med:
        return jsonify({'success': False, 'error': 'Medicamento nao encontrado.'}), 404
    if request.method == 'DELETE':
        db.session.delete(med)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Medicamento removido.'})
    
    dados = request.get_json(silent=True) or {}
    if 'nome'           in dados: med.nome           = str(dados['nome'])[:200]
    if 'lote'           in dados: med.lote           = str(dados['lote'])[:50]
    if 'fabricante'     in dados: med.fabricante     = str(dados['fabricante'])[:150]
    if 'quantidade'     in dados: med.quantidade     = int(dados['quantidade'])
    if 'preco_unitario' in dados: med.preco_unitario = float(dados['preco_unitario'])
    if 'codigo_barras'  in dados: med.codigo_barras  = str(dados['codigo_barras'])[:50]
    if 'data_validade'  in dados:
        try:
            med.data_validade = _date.fromisoformat(dados['data_validade'])
        except ValueError:
            return jsonify({'success': False, 'error': 'data_validade invalida. Use YYYY-MM-DD.'}), 400
    db.session.commit()
    return jsonify({'success': True, 'data': med.to_dict()})

@api_bp.route('/v1/medicamentos/barcode/<codigo>', methods=['GET'])
@csrf.exempt
@api_key_required
def api_buscar_barcode(codigo):
    rede         = request.rede_autenticada
    codigo_limpo = ''.join(c for c in codigo if c.isalnum() or c == '-')[:50]
    med          = Medicamento.query.filter_by(codigo_barras=codigo_limpo, rede_id=rede.id).first()
    if med:
        return jsonify({'success': True, 'data': med.to_dict()})
    return jsonify({'success': False, 'message': 'Nao encontrado'}), 404

@api_bp.route('/v1/filiais', methods=['GET'])
@csrf.exempt
@api_key_required
def api_listar_filiais():
    rede = request.rede_autenticada
    filiais = Usuario.query.filter_by(rede_id=rede.id, perfil='filial').order_by(Usuario.id).all()
    data = [
        {
            'id':   f.id,
            'nome': f.filial_nome or f.nome_exibir or f.username,
            'username': f.username,
        }
        for f in filiais
    ]
    return jsonify({'success': True, 'total': len(data), 'data': data})
