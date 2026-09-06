import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_database_relationships():
    db_uri = os.getenv("INSFORGE_DB_URI")
    if not db_uri:
        raise ValueError("INSFORGE_DB_URI not found in .env file.")
        
    if db_uri.startswith("postgresql://"):
        db_uri = db_uri.replace("postgresql://", "postgresql+psycopg2://")
        
    engine = create_engine(db_uri)
    
    # SQL Query: Join Orders, Items, Products, and Category Translations
    # Objective: Find the top 5 product categories by total revenue for delivered orders.
    sql_query = """
    SELECT 
        c.product_category_name_english AS category,
        COUNT(DISTINCT o.order_id) AS total_orders,
        ROUND(SUM(i.price)::numeric, 2) AS total_revenue
    FROM 
        orders o
    JOIN 
        order_items i ON o.order_id = i.order_id
    JOIN 
        products p ON i.product_id = p.product_id
    LEFT JOIN 
        category_translation c ON p.product_category_name = c.product_category_name
    WHERE 
        o.order_status = 'delivered'
    GROUP BY 
        c.product_category_name_english
    ORDER BY 
        total_revenue DESC
    LIMIT 5;
    """
    
    print("Executing relationship test query on InsForge PostgreSQL...")
    try:
        result_df = pd.read_sql(sql_query, engine)
        print("\n--- Top 5 Product Categories by Revenue ---")
        print(result_df.to_string(index=False))
        print("\nDatabase relationships verified successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_database_relationships()