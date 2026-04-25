import os
import json
import uuid
import sqlite3
import pandas as pd
from datetime import datetime
from itertools import product

from flask import (
    Flask,
    flash,
    render_template,
    request,
    redirect,
    session,
    jsonify,
    send_file,
    url_for,
    send_from_directory
)

from werkzeug.utils import secure_filename

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# ===============================
# APP INIT
# ===============================

app = Flask(__name__)
app.secret_key = "ethnic123"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_PATH = "/tmp/store.db"
# ===============================
# DB CONNECTION
# ===============================
def get_db():
    con = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )
    con.row_factory = sqlite3.Row
    return con

# ===============================
# DB FUNCTIONS
# ===============================
def get_all_categories():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT id, name FROM categories")
    categories = cur.fetchall()
    con.close()
    return categories

def get_all_products():
    con = get_db()
    con.row_factory = sqlite3.Row  # ← important!
    cur = con.cursor()

    rows = cur.execute("""
        SELECT id, name, category, price, mrp, discount_price, stock,
               description, cloth_type, material, occasion, color,
               size, status
        FROM products
        WHERE status='active'
        ORDER BY id DESC
    """).fetchall()

    products = []

    for r in rows:
        p = dict(r)

        # GET FRONT IMAGE
        img = cur.execute("""
            SELECT image_url
            FROM product_images
            WHERE product_id=? AND image_type='front'
            LIMIT 1
        """, (p["id"],)).fetchone()

        p["image"] = img["image_url"] if img else None

        # GET SIZES
        sizes = cur.execute("""
            SELECT size, stock, extra_price
            FROM product_sizes
            WHERE product_id=?
            ORDER BY 
                CASE size
                    WHEN 'S' THEN 1
                    WHEN 'M' THEN 2
                    WHEN 'L' THEN 3
                    WHEN 'XL' THEN 4
                    WHEN 'XXL' THEN 5
                    ELSE 6
                END
        """, (p["id"],)).fetchall()

        # convert sizes to dicts
        p["sizes"] = [dict(s) for s in sizes]

        products.append(p)

    con.close()
    return products


import json

@app.route("/get_reviews/<int:pid>")
def get_reviews(pid):

    conn = sqlite3.connect("store.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM reviews WHERE product_id=? ORDER BY id DESC", (pid,))
    rows = cur.fetchall()

    reviews = []

    for r in rows:

        images = []

        # FIX HERE
        if r["images"] and r["images"] != "[]":
            try:
                images = json.loads(r["images"])
            except:
                images = []

        reviews.append({
            "id": r["id"],
            "name": r["name"],
            "rating": r["rating"],
            "review": r["review"],
            "created_at": r["created_at"],
            "images": images
        })

    conn.close()

    return jsonify(reviews)
# ---------- HOME ----------
@app.route("/")
def home():
    products = get_all_products()       # get all products
    categories = get_all_categories()   # get all categories
    return render_template("index.html", products=products, categories=categories)


# ---------- PRODUCT DETAIL ----------@app.route("/product/<int:id>")
@app.route("/product/<int:id>")
def product_detail(id):
    con = get_db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Fetch product
    cur.execute("SELECT * FROM products WHERE id=?", (id,))
    row = cur.fetchone()

    if not row:
        con.close()
        return "Product not found", 404

    product = dict(row)

    # Calculate discount price if MRP exists
    mrp = product.get("mrp", 0)               # Original price
    discount_price = product.get("discount_price", 0)  # Discount amount
    selling_price = mrp - discount_price if mrp > 0 else product.get("price", 0)

    product["mrp"] = mrp
    product["discount_price"] = discount_price
    product["price"] = selling_price  # Final price after discount

    # GET ALL IMAGES FOR PRODUCT
    images = cur.execute("""
        SELECT image_url
        FROM product_images
        WHERE product_id=?
        ORDER BY
            CASE image_type
                WHEN 'front' THEN 1
                WHEN 'back' THEN 2
                ELSE 3
            END
    """, (product["id"],)).fetchall()

    # Convert to list of filenames
    product["images"] = [img["image_url"] for img in images] if images else []

    # Fetch sizes
    cur.execute("""
        SELECT size, stock, extra_price
        FROM product_sizes
        WHERE product_id=?
        ORDER BY 
            CASE size
                WHEN 'S' THEN 1
                WHEN 'M' THEN 2
                WHEN 'L' THEN 3
                WHEN 'XL' THEN 4
                WHEN 'XXL' THEN 5
                ELSE 6
            END
    """, (id,))

    sizes = [dict(s) for s in cur.fetchall()]

    con.close()

   

    return render_template(
        "product.html",
        p=product,
        sizes=sizes,
        
    )

# ---------- ADD TO CART ----------from flask import flash, redirect, request, session
from flask import flash, redirect, request, session

@app.route("/add_to_cart/<int:pid>", methods=["POST"])
def add_to_cart(pid):
    size = request.form.get("size")
    if not size:
        return jsonify({"status":"error", "message":"Please select a size!"})

    con = get_db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    product = cur.execute(
        "SELECT price, name FROM products WHERE id=?", (pid,)
    ).fetchone()

    if not product:
        return jsonify({"status":"error", "message":"Invalid product!"})

    price = product["price"]
    name = product["name"]

    size_data = cur.execute(
        "SELECT extra_price FROM product_sizes WHERE product_id=? AND size=?",
        (pid, size)
    ).fetchone()

    if size_data:
        price += size_data["extra_price"] or 0

    cart_item = cur.execute(
        "SELECT id FROM cart WHERE product_id=? AND size=?",
        (pid, size)
    ).fetchone()

    if cart_item:
        con.close()
        return jsonify({
            "status":"exists",
            "message":f"{name} (Size {size}) is already in your cart"
        })

    # insert item
    cur.execute(
        "INSERT INTO cart(product_id, size, price, qty) VALUES (?, ?, ?, 1)",
        (pid, size, price)
    )

    con.commit()

    # count total cart items
    row = cur.execute("SELECT SUM(qty) as total FROM cart").fetchone()
    cart_count = row["total"] if row["total"] else 0

    con.close()

    return jsonify({
        "status":"success",
        "message":f"Added {name} (Size {size}) to cart",
        "cart_count": cart_count
    })

@app.route("/shop")
def shop():
    con = get_db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rows = cur.execute("""
        SELECT p.*, c.name as category_name
        FROM products p
        LEFT JOIN categories c ON p.category = c.id
        WHERE p.status='active'
        ORDER BY p.position ASC
    """).fetchall()

    products = []

    for r in rows:
        p = dict(r)   # convert Row → dict

        sizes = cur.execute("""
            SELECT size, stock, extra_price
            FROM product_sizes
            WHERE product_id=?
        """, (p["id"],)).fetchall()

        p["sizes"] = sizes  # now Jinja can read it
        products.append(p)

    categories = cur.execute("SELECT id, name FROM categories").fetchall()

    con.close()
    return render_template("shop.html", products=products, categories=categories)




# ---------- ADD CATEGORY ----------
@app.route("/admin/add_category", methods=["GET", "POST"])
def add_category():
    if request.method == "POST":
        name = request.form["name"]
        con = get_db()
        cur = con.cursor()
        cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        con.commit()
        con.close()
        return redirect("/admin/dashboard")
    return render_template("admin/add_category.html")


import os
import uuid
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "static/uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route("/admin/add_product", methods=["GET", "POST"])
def add_product():
    con = get_db()
    cur = con.cursor()

    # Fetch categories for dropdown
    cur.execute("SELECT id, name FROM categories")
    categories = cur.fetchall()

    if request.method == "POST":
        # ----------------------------
        # 1️⃣ Get all product info
        # ----------------------------
        name = request.form.get("name", "").strip()
        mrp = float(request.form.get("mrp", 0))
        category_id = request.form.get("category_id")
        description = request.form.get("description", "").strip()
        cloth_type = request.form.get("cloth_type", "").strip()
        material = request.form.get("material", "").strip()
        occasion = request.form.get("occasion", "").strip()
        color = request.form.get("color", "").strip()
        discount_price = float(request.form.get("discount_price", 0))
        price = mrp - discount_price  # Selling price after discount

        # ----------------------------
        # 2️⃣ Insert product into database
        # ----------------------------
        cur.execute("""
        INSERT INTO products
        (name, description, category, mrp, price, discount_price,
         cloth_type, material, occasion, color)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            name,
            description,
            category_id,
            mrp,
            price,
            discount_price,
            cloth_type,
            material,
            occasion,
            color
        ))
        product_id = cur.lastrowid

        # ----------------------------
        # 3️⃣ Save sizes
        # ----------------------------
        sizes = ["S","M","L","XL","XXL","3XL","4XL","5XL"]
        for size in sizes:
            stock = request.form.get(f"stock_{size}")
            extra_price = request.form.get(f"price_{size}")
            stock = int(stock) if stock else 0
            extra_price = float(extra_price) if extra_price else 0
            if stock > 0:
                cur.execute("""
                INSERT INTO product_sizes(product_id, size, stock, extra_price)
                VALUES (?,?,?,?)
                """, (product_id, size, stock, extra_price))

        # ----------------------------
        # 4️⃣ Save front/back images (no labels)
        # ----------------------------
        def save_images(files, image_type):
            for file in files:
                if file and file.filename != "":
                    filename = secure_filename(file.filename)
                    filename = str(uuid.uuid4()) + "_" + filename
                    file.save(os.path.join(UPLOAD_FOLDER, filename))
                    cur.execute("""
                    INSERT INTO product_images
                    (product_id, image_type, image_url)
                    VALUES (?,?,?)
                    """, (product_id, image_type, filename))

        save_images(request.files.getlist("front_images"), "front")
        save_images(request.files.getlist("back_images"), "back")

        # ----------------------------
        # 5️⃣ Save extra images with labels
        # ----------------------------
        extra_files = request.files.getlist("extra_images[]")
        extra_labels = request.form.getlist("extra_label[]")
        for i, file in enumerate(extra_files):
            if file and file.filename != "":
                filename = secure_filename(file.filename)
                filename = str(uuid.uuid4()) + "_" + filename
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                label = extra_labels[i] if i < len(extra_labels) else None
                cur.execute("""
                    INSERT INTO product_images (product_id, image_type, image_url, label)
                    VALUES (?, ?, ?, ?)
                """, (product_id, "extra", filename, label))

        # ----------------------------
        # 6️⃣ Commit & redirect
        # ----------------------------
        con.commit()
        con.close()
        return redirect("/admin/add_product")  # success popup handled in frontend

    # ----------------------------
    # GET request: render form
    # ----------------------------
    con.close()
    return render_template("admin/add_product.html", categories=categories)
# ===============================
# RUN
# ===============================


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')



# ---------- ADMIN ----------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin123":
            session["admin"] = True
            return redirect("/admin/dashboard")
        return "Invalid Login"
    return render_template("admin_login.html")

# ---------- DASHBOARD ----------
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    con = get_db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Fetch categories
    cur.execute("SELECT * FROM categories")
    categories = cur.fetchall()

    # Fetch products
    cur.execute("""
        SELECT * FROM products
        ORDER BY id DESC
    """)
    products = cur.fetchall()

    product_list = []

    for p in products:

        # ---------- FETCH SIZES ----------
        cur.execute("""
            SELECT size, stock, extra_price
            FROM product_sizes
            WHERE product_id=?
        """, (p["id"],))

        size_rows = cur.fetchall()

        sizes = {r["size"]: r["stock"] for r in size_rows}
        sizes_extra = {r["size"]: r["extra_price"] for r in size_rows}

        # ---------- FETCH IMAGES ----------
        cur.execute("""
            SELECT image_type, image_url, label
            FROM product_images
            WHERE product_id=?
        """, (p["id"],))

        images = cur.fetchall()

        front_images = []
        back_images = []
        extra_images = []

        for img in images:
            if img["image_type"] == "front":
                front_images.append(img["image_url"])
            elif img["image_type"] == "back":
                back_images.append(img["image_url"])
            elif img["image_type"] == "extra":
                extra_images.append({
                    "url": img["image_url"],
                    "label": img["label"]
                })
        cur.execute("""
SELECT * FROM products
ORDER BY position ASC
""")
        # ---------- CATEGORY NAME ----------
        category_name = next(
            (c["name"] for c in categories if c["id"] == p["category"]),
            "None"
        )

        product_list.append({
            "id": p["id"],
            "name": p["name"],
            "category": category_name,
            "price": p["price"],
            "mrp": p["mrp"],
            "discount_price": p["discount_price"],
            "cloth_type": p["cloth_type"],
            "material": p["material"],
            "occasion": p["occasion"],
            "color": p["color"],

            # SIZE DATA
            "sizes": sizes,
            "sizes_extra": sizes_extra,

            # IMAGES
            "front_images": front_images,
            "back_images": back_images,
            "extra_images": extra_images
        })

    # Fetch orders
    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()

    con.close()

    return render_template(
        "admin_dashboard.html",
        categories=categories,
        products=product_list,
        orders=orders
    )

@app.route("/update_cart/<int:cart_id>", methods=["POST"])
def update_cart(cart_id):
    qty = int(request.form.get("qty",1))
    con = get_db()
    cur = con.cursor()
    cur.execute("UPDATE cart SET qty=? WHERE id=?", (qty, cart_id))
    con.commit()
    con.close()
    return redirect("/cart")

@app.route("/admin/update_product_order", methods=["POST"])
def update_product_order():

    data = request.get_json()
    con = get_db()
    cur = con.cursor()

    for item in data:
        cur.execute(
            "UPDATE products SET position=? WHERE id=?",
            (item["position"], item["id"])
        )

    con.commit()
    con.close()

    return {"status":"ok"}

    
@app.route("/admin/edit_product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    if not session.get("admin"):
        return redirect("/admin")

    con = get_db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # -------------------------
    # Fetch Product
    # -------------------------
    cur.execute("SELECT * FROM products WHERE id=?", (id,))
    product = cur.fetchone()

    if not product:
        con.close()
        return "Product not found"

    product = dict(product)

    # -------------------------
    # Fetch Sizes
    # -------------------------
    cur.execute("""
        SELECT size, stock, extra_price
        FROM product_sizes
        WHERE product_id=?
    """, (id,))

    size_rows = cur.fetchall()

    size_stock = {}
    size_price = {}

    for r in size_rows:
        size_stock[r["size"]] = r["stock"]
        size_price[r["size"]] = r["extra_price"]

    # -------------------------
    # Fetch Images
    # -------------------------
    cur.execute("""
        SELECT image_type, image_url, label
        FROM product_images
        WHERE product_id=?
    """, (id,))

    rows = cur.fetchall()

    images = {
        "front": [],
        "back": [],
        "extra": []
    }

    for r in rows:
        images[r["image_type"]].append({
            "url": r["image_url"],
            "label": r["label"]
        })

    # -------------------------
    # Fetch Categories
    # -------------------------
    cur.execute("SELECT id,name FROM categories")
    categories = cur.fetchall()
    return render_template(
        "admin/edit_product.html",
        product=product,
        sizes=size_stock,
        prices=size_price,
        images=images,
        categories=categories
    )


@app.route("/add_review/<int:pid>", methods=["POST"])
def add_review(pid):
    import os, json
    from werkzeug.utils import secure_filename

    name = request.form.get("name")
    rating = request.form.get("rating")
    review = request.form.get("review")

    # handle multiple images
    images = request.files.getlist("images")
    saved_images = []

    for img in images:
        if img and img.filename != "":
            filename = secure_filename(img.filename)
            path = os.path.join(app.root_path, 'static', 'reviews', filename)
            img.save(path)
            saved_images.append(filename)

    # Convert list to JSON string to store in DB
    images_json = json.dumps(saved_images)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reviews (product_id, name, rating, review, images, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (pid, name, rating, review, images_json))
    conn.commit()
    conn.close()

    return redirect(url_for("product_detail", id=pid))

@app.route("/delete_review/<int:rid>")
def delete_review(rid):

    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT product_id FROM reviews WHERE id=?", (rid,))
    row = cur.fetchone()

    if not row:
        return redirect("/")

    pid = row["product_id"]

    cur.execute("DELETE FROM reviews WHERE id=?", (rid,))
    con.commit()
    con.close()

    return redirect(url_for("product_detail", id=pid))


@app.route("/edit_review/<int:rid>", methods=["GET","POST"])
def edit_review(rid):

    con = get_db()
    cur = con.cursor()

    if request.method == "POST":

        rating = request.form.get("rating")
        review = request.form.get("review")

        cur.execute("""
        UPDATE reviews
        SET rating=?, review=?
        WHERE id=?
        """,(rating,review,rid))

        con.commit()

        cur.execute("SELECT product_id FROM reviews WHERE id=?", (rid,))
        pid = cur.fetchone()["product_id"]

        con.close()

        return redirect(url_for("product_detail", id=pid))

    cur.execute("SELECT * FROM reviews WHERE id=?", (rid,))
    review = cur.fetchone()

    return render_template("edit_review.html", review=review)



    # =========================
    # UPDATE PRODUCT
    # =========================
    if request.method == "POST":

        name = request.form.get("name")
        description = request.form.get("description")

        mrp = float(request.form.get("mrp") or 0)
        price = float(request.form.get("price") or 0)
        discount_price = float(request.form.get("discount_price") or 0)

        category_id = request.form.get("category_id")

        cloth_type = request.form.get("cloth_type")
        material = request.form.get("material")
        occasion = request.form.get("occasion")
        color = request.form.get("color")

        # -------------------------
        # Update product table
        # -------------------------
        cur.execute("""
        UPDATE products SET
            name=?,
            description=?,
            category=?,
            mrp=?,
            price=?,
            discount_price=?,
            cloth_type=?,
            material=?,
            occasion=?,
            color=?
        WHERE id=?
        """,(
            name,
            description,
            category_id,
            mrp,
            price,
            discount_price,
            cloth_type,
            material,
            occasion,
            color,
            id
        ))

        # -------------------------
        # Update Sizes
        # -------------------------
        sizes = ["S","M","L","XL","XXL","3XL","4XL","5XL"]

        for s in sizes:

            stock = int(request.form.get(f"stock_{s}") or 0)
            extra = float(request.form.get(f"extra_{s}") or 0)

            cur.execute("""
            SELECT id FROM product_sizes
            WHERE product_id=? AND size=?
            """,(id,s))

            row = cur.fetchone()

            if row:
                cur.execute("""
                UPDATE product_sizes
                SET stock=?, extra_price=?
                WHERE product_id=? AND size=?
                """,(stock,extra,id,s))

            else:
                cur.execute("""
                INSERT INTO product_sizes
                (product_id,size,stock,extra_price)
                VALUES (?,?,?,?)
                """,(id,s,stock,extra))

        # -------------------------
        # Upload Images
        # -------------------------
        def save_images(files,labels,image_type):

            for i,file in enumerate(files):

                if file and file.filename!="":

                    filename = secure_filename(file.filename)
                    filename = str(uuid.uuid4()) + "_" + filename

                    file.save(os.path.join(UPLOAD_FOLDER,filename))

                    label = labels[i] if i < len(labels) else None

                    cur.execute("""
                    INSERT INTO product_images
                    (product_id,image_type,image_url,label)
                    VALUES (?,?,?,?)
                    """,(id,image_type,filename,label))

        save_images(
            request.files.getlist("front_images[]"),
            request.form.getlist("front_labels[]"),
            "front"
        )

        save_images(
            request.files.getlist("back_images[]"),
            request.form.getlist("back_labels[]"),
            "back"
        )

        save_images(
            request.files.getlist("extra_images[]"),
            request.form.getlist("extra_label[]"),
            "extra"
        )

        con.commit()
        con.close()

        return redirect("/admin/dashboard")

    # -------------------------
    # Render Page
    # -------------------------
    con.close()

    return render_template(
        "admin/edit_product.html",
        product=product,
        categories=categories,
        size_stock=size_stock,
        size_price=size_price,
        images=images,
        all_sizes=["S","M","L","XL","XXL","3XL","4XL","5XL"]
    )


def get_counts():
    con = get_db()
    cur = con.cursor()
    cart = cur.execute("SELECT COUNT(*) FROM cart").fetchone()[0]
    wish = cur.execute("SELECT COUNT(*) FROM wishlist").fetchone()[0]
    con.close()
    return cart, wish

@app.before_request
def init_wishlist():
    if "wishlist" not in session:
        session["wishlist"] = []
        

@app.route("/wishlist")
def wishlist():
    if "wishlist" not in session or session["wishlist"] is None:
        session["wishlist"] = []

    wish_ids = session["wishlist"]
    wish_count = len(wish_ids)

    if not wish_ids:
        return render_template("wishlist.html", products=[], wish_count=wish_count)

    q = ",".join("?" * len(wish_ids))
    con = get_db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    products = cur.execute(f"""
        SELECT p.*, pi.image_url AS image
        FROM products p
        LEFT JOIN product_images pi
          ON pi.product_id = p.id AND pi.image_type='front'
        WHERE p.id IN ({q})
    """, wish_ids).fetchall()
    con.close()

    return render_template("wishlist.html", products=products, wish_count=wish_count)



@app.route("/remove_cart/<int:cart_id>", methods=["POST"])
def remove_cart(cart_id):
    con = get_db()
    cur = con.cursor()

    cur.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
    
    con.commit()
    con.close()

    return redirect("/cart")


@app.route("/add_wishlist/<int:pid>")
def add_wishlist(pid):
    if "wishlist" not in session or session["wishlist"] is None:
        session["wishlist"] = []

    if pid not in session["wishlist"]:
        session["wishlist"].append(pid)
        session.modified = True
        return jsonify({
            "status": "success",
            "wish": len(session["wishlist"]),
            "message": "Added to wishlist!"
        })
    else:
        return jsonify({
            "status": "exists",
            "wish": len(session["wishlist"]),
            "message": "Already in wishlist!"
        })

@app.route("/remove_wishlist/<int:pid>")
def remove_wishlist(pid):

    if "wishlist" not in session or session["wishlist"] is None:
        session["wishlist"] = []

    if pid in session["wishlist"]:
        session["wishlist"].remove(pid)
        session.modified = True

    return jsonify({
        "status": "success",
        "wish": len(session["wishlist"]),
        "message": "Removed from wishlist!"
    })

@app.route("/counts")
def counts():
    con = get_db()
    cur = con.cursor()
    row = cur.execute("SELECT COALESCE(SUM(qty),0) FROM cart").fetchone()
    cart_count = int(row[0])
    con.close()

    # Wishlist session
    if "wishlist" not in session or session["wishlist"] is None:
        session["wishlist"] = []

    wish_count = len(session["wishlist"])

    return jsonify({
        "cart": cart_count,
        "wish": wish_count
    })

@app.route("/place-order", methods=["POST"])
def place_order():
    con = None
    try:
        pid = request.form.get("pid")
        size = request.form.get("size")
        name = request.form.get("name")
        phone = request.form.get("phone")
        method = request.form.get("pay")

        if not size:
            return jsonify({"error": "Select size"})

        con = get_db()
        cur = con.cursor()
        cur.execute("BEGIN IMMEDIATE")

        p = cur.execute(
            "SELECT name, price FROM products WHERE id=?",
            (pid,)
        ).fetchone()

        if not p:
            con.rollback()
            return jsonify({"error": "Product not found"})

        pname, price = p["name"], p["price"]

        stock = cur.execute("""
            SELECT stock FROM product_sizes
            WHERE product_id=? AND size=?
        """, (pid, size)).fetchone()

        if not stock or stock["stock"] <= 0:
            con.rollback()
            return jsonify({"error": "Size out of stock"})

        cur.execute("""
    INSERT INTO orders
    (customer_name, phone, total, payment_method, status)
    VALUES (?,?,?,?,?)
""", (name, phone, price, method.upper(), "PLACED"))

        cur.execute("""
            UPDATE product_sizes
            SET stock = stock - 1
            WHERE product_id=? AND size=?
        """, (pid, size))

        con.commit()
        return jsonify({"type": method})

    except sqlite3.OperationalError as e:
        return jsonify({"error": "Database busy, try again"})

    finally:
        if con:
            con.close()



@app.route("/admin/export")
def export_excel():
    con = get_db()
    df = pd.read_sql_query("SELECT * FROM orders", con)
    con.close()

    file = "orders.xlsx"
    df.to_excel(file, index=False)
    return send_file(file, as_attachment=True)

@app.route("/admin/orders")
def admin_orders():
    con = get_db()              # <-- USE store.db
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    orders = cur.execute("""
    SELECT id, customer_name, phone, total,
           payment_method, status
    FROM orders
    ORDER BY id DESC
""").fetchall()


    con.close()
    return render_template("admin_orders.html", orders=orders)

# Show checkout page

# Show checkout page for a specific product
@app.route("/buy_now/<int:pid>", methods=["GET"])
def buy_now(pid):

    size = request.args.get("size")  # selected size from product page

    con = get_db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Get product with front image
    product = cur.execute("""
        SELECT 
            p.id,
            p.name,
            p.price,
            pi.image_url AS image
        FROM products p
        LEFT JOIN product_images pi
            ON pi.product_id = p.id AND pi.image_type = 'front'
        WHERE p.id = ?
    """, (pid,)).fetchone()

    if not product:
        con.close()
        return "Product not found", 404

    base_price = product["price"]
    final_price = base_price

    # If size selected → add extra price
    if size:
        size_data = cur.execute("""
            SELECT extra_price, stock
            FROM product_sizes
            WHERE product_id=? AND size=?
        """, (pid, size)).fetchone()

        if size_data:
            final_price = base_price + (size_data["extra_price"] or 0)

    # Fetch sizes
    sizes = cur.execute("""
        SELECT size, stock, extra_price
        FROM product_sizes
        WHERE product_id=?
        ORDER BY 
            CASE size
                WHEN 'S' THEN 1
                WHEN 'M' THEN 2
                WHEN 'L' THEN 3
                WHEN 'XL' THEN 4
                WHEN 'XXL' THEN 5
                ELSE 6
            END
    """, (pid,)).fetchall()

    con.close()

   
   
    return render_template(
        "checkout.html",
        product=product,
        sizes=sizes,
        selected_size=size,
        price=final_price
    )
# ---------- EDIT CATEGORY ----------
@app.route("/admin/edit_category/<int:id>", methods=["GET", "POST"])
def edit_category(id):
    con = get_db()
    cur = con.cursor()
    if request.method == "POST":
        name = request.form["name"]
        cur.execute("UPDATE categories SET name=? WHERE id=?", (name, id))
        con.commit()
        con.close()
        return redirect("/admin/dashboard")
    cur.execute("SELECT * FROM categories WHERE id=?", (id,))
    category = cur.fetchone()
    con.close()
    return render_template("admin/edit_category.html", category=category)

# ---------- DELETE CATEGORY ----------
@app.route("/admin/delete_category/<int:id>")
def delete_category(id):
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM categories WHERE id=?", (id,))
    con.commit()
    con.close()
    return redirect("/admin/dashboard")

# ---------- DELETE PRODUCT ----------
@app.route("/admin/delete_product/<int:id>")
def delete_product(id):
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM products WHERE id=?", (id,))
    con.commit()
    con.close()
    return redirect("/admin/dashboard")


@app.route("/admin/reorder_products", methods=["POST"])
def reorder_products():
    if not session.get("admin"):
        return jsonify({"status":"error", "msg":"Unauthorized"})
    
    data = request.get_json()
    con = get_db()
    cur = con.cursor()

    # Expecting data = {'order':[{'id':1,'position':1}, ...]}
    for item in data['order']:
        cur.execute("UPDATE products SET position=? WHERE id=?", (item['position'], item['id']))
    con.commit()
    con.close()
    return jsonify({"status":"success"})

@app.context_processor
def inject_global_counts():
    con = get_db()
    cur = con.cursor()
    row = cur.execute("SELECT COALESCE(SUM(qty),0) FROM cart").fetchone()
    cart_count = int(row[0])
    con.close()

    if "wishlist" not in session or session["wishlist"] is None:
        session["wishlist"] = []

    return dict(
        cart_count=cart_count,
        wish_count=len(session["wishlist"])
    )


from flask import session, jsonify

@app.route("/clear_wishlist")
def clear_wishlist():
    session.pop("wishlist", None)   # remove wishlist from session
    session.modified = True
    return jsonify({"status": "success", "message": "Wishlist cleared"})


# ---------- CART ----------
@app.route("/cart")
def cart():
    con = get_db()
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Fetch cart items with product info
    items = cur.execute("""
        SELECT c.id AS cart_id, c.product_id, c.size AS selected_size, c.price, c.qty,
               p.name, p.description, p.cloth_type, p.material, p.color, p.occasion,
               pi.image_url AS image
        FROM cart c
        JOIN products p ON p.id = c.product_id
        LEFT JOIN product_images pi
          ON p.id = pi.product_id AND pi.image_type='front'
    """).fetchall()

    # Convert rows to list of dicts
    items = [dict(item) for item in items]

    # Fetch sizes for each product
    for item in items:
        sizes = cur.execute(
            "SELECT size, stock, extra_price FROM product_sizes WHERE product_id=? ORDER BY size",
            (item["product_id"],)
        ).fetchall()
        item["sizes"] = [dict(s) for s in sizes]

    # Grand total
    grand = sum(item["price"] * item["qty"] for item in items)

    con.close()
    return render_template("cart.html", items=items, grand=grand)



# ---------- CHECKOUT ----------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    con = get_db()
    cur = con.cursor()

    # Fetch all cart items
    items = cur.execute("""
        SELECT c.product_id, p.name, c.size, c.price, c.qty, pi.image_url AS image
        FROM cart c
        JOIN products p ON p.id = c.product_id
        LEFT JOIN product_images pi ON p.id = pi.product_id AND pi.image_type='front'
    """).fetchall()

    grand_total = sum(i['price']*i['qty'] for i in items)

    # POST: handle form submission
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        pay = request.form.get("pay", "").strip()

        missing_fields = []
        if not name: missing_fields.append("Name")
        if not phone: missing_fields.append("Phone")
        if not address: missing_fields.append("Address")
        if not pay: missing_fields.append("Payment Method")

        if missing_fields:
            warning = "⚠️ Please fill all required fields: " + ", ".join(missing_fields)
            return render_template("checkout.html", items=items, grand_total=grand_total, warning=warning,
                                   form_data=request.form)

        # Insert order
        cur.execute("""
            INSERT INTO orders(customer_name, phone, total, payment_method)
            VALUES (?, ?, ?, ?)
        """, (name, phone, grand_total, pay))
        oid = cur.lastrowid

        # Insert order items & update stock
        for i in items:
            cur.execute("""
                INSERT INTO order_items(order_id, product_id, product_name, price, quantity, size)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (oid, i['product_id'], i['name'], i['price'], i['qty'], i['size']))

            cur.execute("""
                UPDATE product_sizes
                SET stock = stock - ?
                WHERE product_id = ? AND size = ?
            """, (i['qty'], i['product_id'], i['size']))

        # Clear cart
        cur.execute("DELETE FROM cart")
        con.commit()
        con.close()

        return render_template("order_success.html", total=grand_total)

    # GET: just show checkout page
    con.close()
    return render_template("checkout.html", items=items, grand_total=grand_total)

# ---------- CONTACT FORM SAVE TO EXCEL ----------
from flask import request, redirect
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

@app.route("/contact", methods=["POST"])
def contact():

    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    message = request.form.get("message")

    sender_email = "patil123sidd@gmail.com"
    receiver_email = "patil123sidd@gmail.com"
    password = "wbonwhgnadserhuu"

    msg = MIMEMultipart()

    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = f"New Customer Message from {name}"
    msg["Reply-To"] = email

    body = f"""
Customer Inquiry

Name: {name}
Email: {email}
Phone: {phone}

Message:
{message}
"""

    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
        server.quit()

        print("Email sent successfully")

    except Exception as e:
        print("Email error:", e)

    return redirect("/")

# ---------- LOGOUT ----------
@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect("/admin")

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(debug=True)
