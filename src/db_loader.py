import os
import pandas as pd
from sqlalchemy import create_engine
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure paths
BASE_DIR = os.getenv("PROJECT_ROOT_DIR", Path(__file__).parent.parent)
CLEANED_DIR = BASE_DIR / "data_cleaned"

def get_table_name(filename):
    """Simplify filenames into clean SQL table names."""
    name = filename.replace('cleaned_', '').replace('olist_', '').replace('_dataset', '')
    if name == 'product_category_name_translation':
        return 'category_translation'
    return name

def load_data_to_postgres():
    db_uri = os.getenv("INSFORGE_DB_URI")
    if not db_uri:
        raise ValueError("INSFORGE_DB_URI not found in .env file.")
    
    # SQLAlchemy requires the postgresql+psycopg2 dialect for the psycopg2 driver
    if db_uri.startswith("postgresql://"):
        db_uri = db_uri.replace("postgresql://", "postgresql+psycopg2://")

    print("Connecting to InsForge PostgreSQL...")
    engine = create_engine(db_uri)

    for file_path in CLEANED_DIR.glob('*.csv'):
        table_name = get_table_name(file_path.stem)
        print(f"Loading {file_path.name} into table '{table_name}'...")
        
        # Load in chunks to prevent memory overload with large datasets
        df = pd.read_csv(file_path)
        df.to_sql(table_name, engine, if_exists='replace', index=False, chunksize=10000)
        print(f"Successfully loaded {len(df)} rows into '{table_name}'.")

if __name__ == "__main__":
    load_data_to_postgres()
    print("All datasets successfully loaded into the database.")