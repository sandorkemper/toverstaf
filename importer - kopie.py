# importer.py
import csv
import os
from bcrypt import hashpw, gensalt
from models import db, SOC2FrameworkControl, ISO27001FrameworkControl, User, UserRole, Client, MasterControl, ContactPerson
from app import app  # reuse the same Flask app & db

def create_initial_data():
    """Creëert de initiële admin-gebruiker en testklant."""
    with app.app_context():
        if not User.query.filter_by(email='admin@example.com').first():
            hashed_password = hashpw("wachtwoord".encode('utf-8'), gensalt()).decode('utf-8')
            admin_user = User(
                name="Admin",
                email="admin@example.com",
                password_hash=hashed_password,
                role=UserRole.BEHEERDER,
                is_approved=True
            )
            db.session.add(admin_user)
            print("Initial admin user created.")

        if not Client.query.filter_by(name='Testklant B.V.').first():
            test_client = Client(
                name="Testklant B.V.",
                client_number="KL-001",
                address="Teststraat 1",
                zip_code="1234 AB",
                city="Teststad",
                chamber_of_commerce_number="12345678"
            )
            db.session.add(test_client)
            db.session.commit()

            test_contact = ContactPerson(
                client_id=test_client.id,
                name="Jan van Veen",
                email="jan.vanveen@testklant.nl",
                phone_number="06-12345678",
                is_primary=True
            )
            db.session.add(test_contact)
            db.session.commit()
            print("Initial test client and contact person created.")


def import_csv_to_db(filepath, model):
    """Hulpfunctie om CSV-bestanden in de database te importeren."""
    with open(filepath, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file, delimiter=';')
        rows_to_add = []
        for row in reader:
            if model.__name__ == 'MasterControl':
                if filepath == 'SOC2 framework.csv':
                    rows_to_add.append(MasterControl(
                        framework="SOC2",
                        series=row.get('Series'),
                        series_description=row.get('Series description'),
                        tsc_series=row.get('TSC Series'),
                        tsc_description_series=row.get('TSC description Series'),
                        sub=row.get('Sub'),
                        points_of_focus=row.get('Points of focus')
                    ))
                else:  # ISO27001 file
                    rows_to_add.append(MasterControl(
                        framework="ISO27001",
                        hoofdstuk=row.get('hoofdstuk'),
                        naam_hoofdstuk=row.get('naam_hoofdstuk'),
                        beheersmaatregel_id=row.get('beheersmaatregel_id'),
                        beheersmaatregel_naam=row.get('beheersmaatregel_naam'),
                        beheersmaatregel_inhoud=row.get('beheersmaatregel_inhoud')
                    ))
            else: # For specific framework tables
                rows_to_add.append(model(**row))

        db.session.bulk_save_objects(rows_to_add)
        db.session.commit()
        print(f"Imported {len(rows_to_add)} rows from {filepath} into {model.__name__}")

def main():
    with app.app_context():
        if os.path.exists("audit_applicatie.db"):
            os.remove("audit_applicatie.db")
            print("Existing database file removed.")

        db.create_all()
        print("Database schema created.")

        # Import CSVs
        # import_csv_to_db('SOC2 framework.csv', SOC2FrameworkControl)
        # import_csv_to_db('ISO27001 framework.csv', ISO27001FrameworkControl)
        import_csv_to_db('SOC2 framework.csv', MasterControl)
        import_csv_to_db('ISO27001 framework.csv', MasterControl)

        # Create initial data
        create_initial_data()
        
    print("Database initialization complete.")

if __name__ == "__main__":
    main()
