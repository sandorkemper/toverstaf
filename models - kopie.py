# models.py
import datetime
import enum
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship

db = SQLAlchemy()

# ----------------------------
# ENUMS
# ----------------------------
class UserRole(enum.Enum):
    BEHEERDER = "beheerder"
    TEKENEND_PROFESSIONAL = "tekenend_professional"
    DOSSIERMANAGER = "dossiermanager"
    TEAMLID = "teamlid"
    PENDING = "pending"
    KLANT = "klant"

class DossierStatus(enum.Enum):
    NIEUW = "nieuw"
    IN_BEHANDELING = "in behandeling"
    AFGEROND = "afgerond"
    GEARCHIVEERD = "gearchiveerd"

class ControlStatus(enum.Enum):
    OPEN = "open"
    IN_UITVOERING = "in_uitvoering"
    AFGEROND = "afgerond"
    NIET_VAN_TOEPASSING = "niet_van_toepassing"

class TaskStatus(enum.Enum):
    OPEN = "open"
    IN_UITVOERING = "in_uitvoering"
    VOLTOOID = "voltooid"

# ----------------------------
# MODELS
# ----------------------------
class User(db.Model):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.PENDING)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    last_login = Column(DateTime)

    # Relaties
    dossier_notes = relationship('DossierNote', back_populates='author')
    dossier_tasks = relationship('DossierTask', back_populates='assigned_to_user')

    def __repr__(self):
        return f"<User(name='{self.name}', role='{self.role.value}')>"

class Client(db.Model):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    client_number = Column(String, unique=True, nullable=False)
    address = Column(String)
    zip_code = Column(String)
    city = Column(String)
    chamber_of_commerce_number = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)

    # Relaties
    dossiers = relationship('Dossier', back_populates='client')
    contact_persons = relationship('ContactPerson', back_populates='client')

    def __repr__(self):
        return f"<Client(name='{self.name}')>"

class ContactPerson(db.Model):
    __tablename__ = 'contact_persons'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String)
    client_id = Column(Integer, ForeignKey('clients.id'))

    # Relaties
    client = relationship('Client', back_populates='contact_persons')

    def __repr__(self):
        return f"<ContactPerson(name='{self.name}')>"

class Dossier(db.Model):
    __tablename__ = 'dossiers'
    id = Column(Integer, primary_key=True)
    dossier_number = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    status = Column(Enum(DossierStatus), nullable=False, default=DossierStatus.NIEUW)
    start_date = Column(DateTime, default=datetime.datetime.now)
    closed_date = Column(DateTime, nullable=True)
    client_id = Column(Integer, ForeignKey('clients.id'))
    created_by_user_id = Column(Integer, ForeignKey('users.id'))

    # Relaties
    client = relationship('Client', back_populates='dossiers')
    controls = relationship('DossierControl', back_populates='dossier')
    notes = relationship('DossierNote', back_populates='dossier')
    documents = relationship('DossierDocument', back_populates='dossier')
    dossier_client_controls = relationship('DossierClientControl', back_populates='dossier')
    created_by_user = relationship('User', foreign_keys=[created_by_user_id])

    def __repr__(self):
        return f"<Dossier(title='{self.title}')>"

class DossierControl(db.Model):
    __tablename__ = 'dossier_controls'
    id = Column(Integer, primary_key=True)
    dossier_id = Column(Integer, ForeignKey('dossiers.id'))
    master_control_id = Column(Integer, ForeignKey('master_controls.id'))
    status = Column(Enum(ControlStatus), default=ControlStatus.OPEN)
    review_status = Column(String)  # 'open', '1st_review', '2nd_review', 'final'
    comments = Column(String)

    # Relaties
    dossier = relationship('Dossier', back_populates='controls')
    master_control = relationship('MasterControl')

    def __repr__(self):
        return f"<DossierControl(dossier_id='{self.dossier_id}', control_id='{self.master_control_id}')>"

class DossierNote(db.Model):
    __tablename__ = 'dossier_notes'
    id = Column(Integer, primary_key=True)
    dossier_id = Column(Integer, ForeignKey('dossiers.id'))
    author_id = Column(Integer, ForeignKey('users.id'))
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    # Relaties
    dossier = relationship('Dossier', back_populates='notes')
    author = relationship('User', back_populates='dossier_notes')

    def __repr__(self):
        return f"<DossierNote(id='{self.id}', author='{self.author.name}')>"

class DossierDocument(db.Model):
    __tablename__ = 'dossier_documents'
    id = Column(Integer, primary_key=True)
    dossier_id = Column(Integer, ForeignKey('dossiers.id'))
    uploaded_by_user_id = Column(Integer, ForeignKey('users.id'))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.now)

    # Relaties
    dossier = relationship('Dossier', back_populates='documents')
    uploaded_by = relationship('User', foreign_keys=[uploaded_by_user_id])

    def __repr__(self):
        return f"<DossierDocument(filename='{self.filename}')>"

class DossierClientControl(db.Model):
    __tablename__ = 'dossier_client_controls'
    id = Column(Integer, primary_key=True)
    dossier_id = Column(Integer, ForeignKey('dossiers.id'), nullable=False)
    master_control_id = Column(Integer, ForeignKey('master_controls.id'), nullable=False)
    client_response = Column(String)
    client_comment = Column(String)

    # Relaties
    dossier = relationship('Dossier', back_populates='dossier_client_controls')
    master_control = relationship('MasterControl', foreign_keys=[master_control_id])

    def __repr__(self):
        return f"<DossierClientControl(dossier_id={self.dossier_id}, control_id={self.master_control_id})>"

class MasterControl(db.Model):
    __tablename__ = 'master_controls'
    id = Column(Integer, primary_key=True)
    framework = Column(String, nullable=False)

    # SOC2 velden
    series = Column(String, nullable=True)
    series_description = Column(String, nullable=True)
    tsc_series = Column(String, nullable=True)
    tsc_description_series = Column(String, nullable=True)
    sub = Column(String, nullable=True)
    points_of_focus = Column(String, nullable=True)

    # ISO27001 velden
    hoofdstuk = Column(String, nullable=True)
    naam_hoofdstuk = Column(String, nullable=True)
    beheersmaatregel_id = Column(String, nullable=True)
    beheersmaatregel_naam = Column(String, nullable=True)
    beheersmaatregel_inhoud = Column(String, nullable=True)

    def __repr__(self):
        return f"<MasterControl(framework='{self.framework}', id='{self.id}')>"

class SOC2FrameworkControl(db.Model):
    __tablename__ = 'soc2_framework_controls'
    id = Column(Integer, primary_key=True)
    framework = Column(String)
    series = Column(String)
    series_description = Column(String)
    tsc_series = Column(String)
    tsc_description_serie = Column(String)
    sub = Column(String)
    points_of_focus = Column(String)

class ISO27001FrameworkControl(db.Model):
    __tablename__ = 'iso27001_framework_controls'
    id = Column(Integer, primary_key=True)
    framework = Column(String)
    hoofdstuk = Column(String)
    naam_hoofdstuk = Column(String)
    beheersmaatregel_id = Column(String)
    beheersmaatregel_naam = Column(String)
    beheersmaatregel_inhoud = Column(String)

class DossierTask(db.Model):
    __tablename__ = 'dossier_tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    status = Column(Enum(TaskStatus), default=TaskStatus.OPEN)
    dossier_id = Column(Integer, ForeignKey('dossiers.id'), nullable=False)
    assigned_to = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    # Relaties
    dossier = relationship('Dossier')
    assigned_to_user = relationship('User', back_populates='dossier_tasks')

# === NIEUW: Per-dossier ACL ===================================================
class DossierACL(db.Model):
    __tablename__ = 'dossier_acl'

    id = Column(Integer, primary_key=True)
    dossier_id = Column(Integer, ForeignKey('dossiers.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # CSV met permissies, bijv: "VIEW,EDIT,MANAGE,REQUEST_DELETE"
    permissions = Column(String, nullable=False, default='')

    granted_by_user_id = Column(Integer, ForeignKey('users.id'))
    granted_at = Column(DateTime, default=datetime.datetime.now)

    dossier = relationship('Dossier')
    user = relationship('User', foreign_keys=[user_id])
    granted_by = relationship('User', foreign_keys=[granted_by_user_id])

    __table_args__ = (
        UniqueConstraint('dossier_id', 'user_id', name='uq_dossier_user'),
    )
