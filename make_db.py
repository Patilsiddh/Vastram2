import sqlite3

DB_NAME = "store.db"

def reset_database():
    con = sqlite3.connect(DB_NAME)
    cur = con.cursor()

    print("🔄 Resetting database...")

    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")

    # =====================================================
    # DROP OLD TABLES (Order matters because of FK)
    # =====================================================
    tables = [
        "order_items",
        "orders",
        "cart",
        "wishlist",         # <-- added wishlist here
        "product_images",
        "product_sizes",
        "products",
        "categories"
    ]

    for table in tables:
        cur.execute(f"DROP TABLE IF EXISTS {table}")

    # =====================================================
    # CREATE TABLES
    # =====================================================

    # ---------------- CATEGORIES ----------------
    cur.execute("""
    CREATE TABLE categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """)

    # ---------------- PRODUCTS ----------------
    cur.execute("""
    CREATE TABLE products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category INTEGER,
        price REAL NOT NULL,
        mrp REAL DEFAULT 0,
        discount_price REAL DEFAULT 0,
        stock INTEGER DEFAULT 0,
        description TEXT,
        cloth_type TEXT,
        material TEXT,
        occasion TEXT,
        color TEXT,
        size TEXT,
        position INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (category)
        REFERENCES categories(id)
        ON DELETE SET NULL
    )
    """)

    # ---------------- PRODUCT SIZES ----------------
    cur.execute("""
    CREATE TABLE product_sizes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        size TEXT NOT NULL,
        stock INTEGER DEFAULT 0,
        extra_price REAL DEFAULT 0,
        FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE CASCADE
    )
    """)

    # ---------------- PRODUCT IMAGES ----------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_images(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        image_type TEXT NOT NULL CHECK(image_type IN ('front','back','extra')),
        image_url TEXT NOT NULL,
        label TEXT,
        FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE CASCADE
    )
    """)

    # ---------------- ORDERS ----------------
    cur.execute("""
    CREATE TABLE orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        email TEXT,
        phone TEXT,
        total REAL,
        payment_method TEXT,
        status TEXT DEFAULT 'PLACED',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ---------------- ORDER ITEMS ----------------
    cur.execute("""
    CREATE TABLE order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        price REAL,
        quantity INTEGER,
        size TEXT,
        FOREIGN KEY (order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE,
        FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE SET NULL
    )
    """)

    # ---------------- CART ----------------
    cur.execute("""
    CREATE TABLE cart(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        product_id INTEGER NOT NULL,
        size TEXT,
        price REAL,
        qty INTEGER DEFAULT 1,
        FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE CASCADE
    )
    """)


    # ---------------- REVIEWS ----------------
    cur.execute("""
CREATE TABLE reviews(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    rating INTEGER NOT NULL,
    review TEXT NOT NULL,
    images TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id)
    REFERENCES products(id)
    ON DELETE CASCADE
)
""")
    # ---------------- WISHLIST ----------------
    cur.execute("""
    CREATE TABLE wishlist(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        session_id TEXT,  -- optional: track user/session
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(product_id),
        FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE CASCADE
    )
    """)

    # =====================================================
    # INDEXES (Performance Optimization)
    # =====================================================
    cur.execute("CREATE INDEX idx_cart_product ON cart(product_id);")
    cur.execute("CREATE INDEX idx_sizes_product ON product_sizes(product_id);")
    cur.execute("CREATE INDEX idx_images_product ON product_images(product_id);")
    cur.execute("CREATE INDEX idx_wishlist_product ON wishlist(product_id);")  # index for wishlist

    # =====================================================
    # COMMIT & CLOSE
    # =====================================================
    con.commit()
    con.close()

    print("✅ Database successfully reset & ready!")


if __name__ == "__main__":
    reset_database()