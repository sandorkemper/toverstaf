# app.py
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, url_for, flash
)
from models import (
    db, Dossier, DossierControl, SOC2FrameworkControl, ISO27001FrameworkControl,
    User, Client, UserRole, DossierNote, DossierDocument, DossierClientControl,
    ContactPerson, DossierACL
)
from bcrypt import checkpw, hashpw, gensalt
import datetime
from sqlalchemy import or_

app = Flask(__name__)
app.config['SECRET_KEY'] = 'jouw_geheime_sleutel'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///audit_applicatie.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,  # <-- zet False als je lokaal zonder HTTPS test
    SESSION_COOKIE_SAMESITE='Lax'
)
db.init_app(app)

# -----------------------------------------------------------------------------
# AUTH DECORATORS (bestaand)
# -----------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            # voor UI: terug naar loginpagina
            if request.accept_mimetypes.accept_html:
                flash("Authenticatie vereist", "error")
                return redirect(url_for('index'))
            return jsonify({"error": "Authenticatie vereist"}), 401
        return f(*args, **kwargs)
    return wrapper

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_role = session.get('user_role')
            if user_role not in roles:
                if request.accept_mimetypes.accept_html:
                    flash("Toegang geweigerd", "error")
                    return redirect(url_for('dashboard'))
                return jsonify({"error": "Toegang geweigerd"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

# -----------------------------------------------------------------------------
# ACL HELPERS (nieuw)
# -----------------------------------------------------------------------------
# Permissies die we nu gebruiken:
#   VIEW, EDIT, MANAGE, REQUEST_DELETE
# (later eenvoudig uitbreiden met REVIEW_1, REVIEW_2, APPROVE_DOCUMENT, DELETE)
ROLE_DEFAULTS = {
    'tekenend_professional': ['VIEW', 'EDIT', 'MANAGE', 'REQUEST_DELETE', 'REVIEW_1', 'REVIEW_2'],
    'dossiermanager': ['VIEW', 'EDIT', 'MANAGE', 'REVIEW_1'],
    'teamlid': [],
    'beheerder': []  # bewust geen bewerkrechten by default
}
ALL_PERMISSIONS = ['VIEW', 'EDIT', 'MANAGE', 'REQUEST_DELETE']

def _parse_perms(s: str):
    return [p for p in (s or '').split(',') if p]

def require_dossier_permission(needed):
    """
    Decorator: vereist permissie(s) op een dossier.
    Route moet een URL-parameter 'dossier_id' hebben: /dossiers/<int:dossier_id>/...
    """
    need = needed if isinstance(needed, (list, tuple)) else [needed]
    def deco(f):
        @wraps(f)
        def wrapper(dossier_id, *args, **kwargs):
            uid = session.get('user_id')
            if not uid:
                return jsonify({"error": "Authenticatie vereist"}), 401
            row = DossierACL.query.filter_by(dossier_id=dossier_id, user_id=uid).first()
            perms = _parse_perms(row.permissions) if row else []
            if not all(p in perms for p in need):
                if request.accept_mimetypes.accept_html:
                    flash("Toegang geweigerd (ACL)", "error")
                    return redirect(url_for('dossiers'))
                return jsonify({"error": "Toegang geweigerd (ACL)"}), 403
            return f(dossier_id, *args, **kwargs)
        return wrapper
    return deco

def grant_default_acl_for_creator(dossier_id: int, creator_user_id: int, creator_role_value: str):
    """
    Geef default ACL aan de maker van een dossier o.b.v. rol.
    Aanroepen direct na het aanmaken van een nieuw dossier.
    """
    defaults = ROLE_DEFAULTS.get(creator_role_value, [])
    if not defaults:
        return
    perms = ",".join(sorted(set(defaults)))
    row = DossierACL.query.filter_by(dossier_id=dossier_id, user_id=creator_user_id).first()
    if row:
        row.permissions = perms
        row.granted_by_user_id = creator_user_id
        row.granted_at = datetime.datetime.utcnow()
    else:
        db.session.add(DossierACL(
            dossier_id=dossier_id,
            user_id=creator_user_id,
            permissions=perms,
            granted_by_user_id=creator_user_id
        ))
    db.session.commit()

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def user_to_dict(user: User):
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role.value,
        'is_approved': user.is_approved,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None
    }

def _next_dossier_number():
    today = datetime.datetime.now().strftime("%Y%m%d")
    last = Dossier.query.filter(Dossier.dossier_number.like(f"D-{today}-%")) \
                        .order_by(Dossier.dossier_number.desc()).first()
    seq = 1
    if last:
        try:
            seq = int(last.dossier_number.split("-")[-1]) + 1
        except Exception:
            seq = 1
    return f"D-{today}-{seq:04d}"

# -----------------------------------------------------------------------------
# ROUTES - AUTH / BASIS
# -----------------------------------------------------------------------------
@app.route('/')
def index():
    # Toon loginpagina / landingspagina
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json or request.form
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()

    if user and user.is_approved and checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        session['user_id'] = user.id
        session['user_role'] = user.role.value  # 'beheerder', 'teamlid', ...
        if request.accept_mimetypes.accept_html:
            return redirect(url_for('dashboard'))
        return jsonify({"message": "Inloggen succesvol", "redirect_url": url_for('dashboard')}), 200
    else:
        if request.accept_mimetypes.accept_html:
            flash("Ongeldige inloggegevens of account nog niet goedgekeurd.", "error")
            return redirect(url_for('index'))
        return jsonify({"error": "Ongeldige inloggegevens of account is nog niet goedgekeurd."}), 401

@app.route('/aanvraag', methods=['GET', 'POST'])
def aanvraag():
    if request.method == 'GET':
        return render_template('aanvraag.html')
    data = request.json or request.form
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"error": "Alle velden zijn verplicht."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "E-mailadres is al in gebruik."}), 409

    hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')
    new_user = User(
        name=name,
        email=email,
        password_hash=hashed_password,
        role=UserRole.PENDING,
        is_approved=False
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Accountaanvraag succesvol verzonden. Wacht op goedkeuring door een beheerder."}), 201

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/teamledenbeheer')
@login_required
@role_required(['beheerder'])
def teamledenbeheer():
    approved_users = User.query.filter_by(is_approved=True).all()
    pending_users = User.query.filter_by(is_approved=False).all()
    return render_template(
        'teamledenbeheer.html',
        approved_users=[user_to_dict(u) for u in approved_users],
        pending_users=[user_to_dict(u) for u in pending_users]
    )

@app.route('/approve_user/<int:user_id>', methods=['POST'])
@login_required
@role_required(['beheerder'])
def approve_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.is_approved = True
        user.role = UserRole.TEAMLID  # default rol bij goedkeuring
        db.session.commit()
        return jsonify({"message": f"Gebruiker {user.name} is goedgekeurd."}), 200
    return jsonify({"error": "Gebruiker niet gevonden."}), 404

@app.route('/deactivate_user/<int:user_id>', methods=['POST'])
@login_required
@role_required(['beheerder'])
def deactivate_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.is_approved = False
        user.role = UserRole.PENDING
        db.session.commit()
        return jsonify({"message": f"Gebruiker {user.name} is gedeactiveerd."}), 200
    return jsonify({"error": "Gebruiker niet gevonden."}), 404

@app.route('/update_role/<int:user_id>', methods=['POST'])
@login_required
@role_required(['beheerder'])
def update_role(user_id):
    data = request.json or request.form
    new_role = data.get('role')  # string: 'beheerder', 'teamlid', ...
    user = User.query.get(user_id)
    valid_values = [r.value for r in UserRole]
    if user and new_role in valid_values:
        user.role = UserRole(new_role)
        db.session.commit()
        return jsonify({"message": f"Rol van gebruiker {user.name} is aangepast naar {new_role}."}), 200
    return jsonify({"error": "Gebruiker of rol niet gevonden."}), 404

@app.route('/clientenbeheer')
@login_required
def clientenbeheer():
    return render_template('clientenbeheer.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_role', None)
    return redirect(url_for('index'))

# -----------------------------------------------------------------------------
# ROUTES - DOSSIERS (nieuw)
# -----------------------------------------------------------------------------
@app.route('/dossiers')
@login_required
def dossiers():
    """Toont alleen dossiers waarop de huidige gebruiker VIEW-rechten heeft."""
    uid = session['user_id']
    # Join via ACL: alle dossiers waar user VIEW in permissions heeft
    # (SQLite-CSV check: eenvoudige LIKE; voor robuuster gedrag kun je perms parsen in Python)
    acl_rows = DossierACL.query.filter_by(user_id=uid).all()
    allowed_ids = []
    for r in acl_rows:
        perms = _parse_perms(r.permissions)
        if 'VIEW' in perms:
            allowed_ids.append(r.dossier_id)
    items = Dossier.query.filter(Dossier.id.in_(allowed_ids)).order_by(Dossier.id.desc()).all() if allowed_ids else []
    # Toon een formulier om een nieuw dossier te starten (alleen TP/Dossiermanager)
    return render_template('dossiers.html', dossiers=items)

@app.route('/dossiers/create', methods=['POST'])
@login_required
def dossiers_create():
    """Nieuw dossier starten: alleen tekenend professional of dossiermanager."""
    if session.get('user_role') not in ('tekenend_professional', 'dossiermanager'):
        flash("Alleen tekenend professional of dossiermanager mag een dossier starten.", "error")
        return redirect(url_for('dossiers'))

    title = (request.form.get('title') or '').strip()
    client_id = request.form.get('client_id')  # optioneel
    if not title:
        flash("Titel is verplicht.", "error")
        return redirect(url_for('dossiers'))

    d = Dossier(
        dossier_number=_next_dossier_number(),
        title=title,
        status=UserRole.TEAMLID and DossierStatus.NIEUW,  # gewoon standaard NIEUW
        client_id=int(client_id) if client_id else None,
        created_by_user_id=session['user_id']
    )
    db.session.add(d)
    db.session.commit()

    # Default ACL voor maker
    grant_default_acl_for_creator(d.id, session['user_id'], session['user_role'])

    flash("Dossier aangemaakt.", "success")
    return redirect(url_for('dossier_detail', dossier_id=d.id))

@app.route('/dossiers/<int:dossier_id>')
@login_required
@require_dossier_permission('VIEW')
def dossier_detail(dossier_id):
    d = Dossier.query.get_or_404(dossier_id)
    acl = DossierACL.query.filter_by(dossier_id=dossier_id).all()
    # Voorbeeld: je kunt hier ook notes/controls/etc. meegeven
    return render_template(
        'dossier_detail.html',
        dossier=d,
        acl=acl,
        ALL_PERMISSIONS=ALL_PERMISSIONS
    )

# --- ACL beheren via POST vanuit de UI ---
@app.route('/dossiers/<int:dossier_id>/acl', methods=['POST'])
@login_required
@require_dossier_permission('MANAGE')
def dossier_acl_update(dossier_id):
    user_id = request.form.get('user_id')
    if not user_id:
        flash("user_id is verplicht.", "error")
        return redirect(url_for('dossier_detail', dossier_id=dossier_id))

    # Lees aangevinkte permissies (checkboxen)
    perms = request.form.getlist('perms')
    perms_csv = ",".join(sorted(set(perms)))

    try:
        user_id_int = int(user_id)
    except Exception:
        flash("user_id moet numeriek zijn.", "error")
        return redirect(url_for('dossier_detail', dossier_id=dossier_id))

    row = DossierACL.query.filter_by(dossier_id=dossier_id, user_id=user_id_int).first()
    if row:
        row.permissions = perms_csv
        row.granted_by_user_id = session['user_id']
        row.granted_at = datetime.datetime.utcnow()
    else:
        db.session.add(DossierACL(
            dossier_id=dossier_id,
            user_id=user_id_int,
            permissions=perms_csv,
            granted_by_user_id=session['user_id']
        ))
    db.session.commit()
    flash("ACL bijgewerkt.", "success")
    return redirect(url_for('dossier_detail', dossier_id=dossier_id))

# (optioneel) JSON endpoints voor tooling of testen
@app.route('/dossiers/<int:dossier_id>/acl.json')
@login_required
@require_dossier_permission('MANAGE')
def dossier_acl_json(dossier_id):
    rows = DossierACL.query.filter_by(dossier_id=dossier_id).all()
    data = [{
        "user_id": r.user_id,
        "permissions": _parse_perms(r.permissions),
        "granted_by": r.granted_by_user_id,
        "granted_at": r.granted_at.strftime('%Y-%m-%d %H:%M:%S') if r.granted_at else None
    } for r in rows]
    return jsonify(data), 200

# -----------------------------------------------------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # maakt nieuwe tabellen zoals dossier_acl aan
    app.run(debug=True)
