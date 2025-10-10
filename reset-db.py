import psycopg2

# Supabase database URL
DB_URL = "postgresql://postgres.lqqhcvfotzowyitgnfgf:Boity%202003@aws-1-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require"

# Tables to truncate in dependency order (child tables after parent tables)
tables = [
    'orderitem',   # child of order & product
    'cartitem',    # child of cart & product
    'delivery',    # child of deliveryguy & order
    'notification',
    'sales',       # child of store & user
    'cart',        # child of user & store
    'order',       # child of user & store & deliveryguy
    'product',     # child of store
    'staff',       # child of store
    'deliveryguy',
    'user',        # child of store
    'store',       # parent table
    'administrater'
]

try:
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Disable foreign key checks temporarily
    cur.execute("SET session_replication_role = replica;")
    
    for table in tables:
        cur.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE;')
        print(f'Truncated {table}')
    
    # Re-enable foreign key checks
    cur.execute("SET session_replication_role = DEFAULT;")
    
    conn.commit()
    cur.close()
    conn.close()
    print("All tables cleared successfully!")

except Exception as e:
    print("Error:", e)
