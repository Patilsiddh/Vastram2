@app.route("/admin/add_product", methods=["GET", "POST"])
def add_product():

    con = sqlite3.connect("store.db")
    cur = con.cursor()

    cur.execute("SELECT id, name FROM categories")
    categories = cur.fetchall()

    if request.method == "POST":

        # ---------- PRODUCT BASIC ----------
        name = request.form["name"]
        price = float(request.form.get("price") or 0)
        mrp = float(request.form.get("mrp") or price)
        discount_price = mrp - price
        category_id = request.form["category_id"]

        # ---------- INSERT PRODUCT ----------
        cur.execute("""
            INSERT INTO products (
                name,
                category,
                price,
                mrp,
                discount_price,
                image
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            name,
            category_id,
            price,
            mrp,
            discount_price,
            ""
        ))

        product_id = cur.lastrowid


        # ---------- HANDLE IMAGES ----------
        import os
        import base64
        import uuid

        upload_folder = "static/uploads"
        os.makedirs(upload_folder, exist_ok=True)

        images_json = request.form.get("images_json")

        print("IMAGES JSON RECEIVED :", images_json)

        front_image = ""

        images = []

        if images_json:
            images = json.loads(images_json)

        for img in images:

            image_type = img.get("type", "Front")
            image_url = img.get("image_url", "").strip()
            label = img.get("name", "")

            if image_url != "":

                image_path = ""

                # ---------- BASE64 IMAGE ----------
                if image_url.startswith("data:image"):

                    try:
                        header, encoded = image_url.split(",", 1)
                        image_data = base64.b64decode(encoded)

                        filename = str(uuid.uuid4()) + ".jpg"
                        filepath = os.path.join(upload_folder, filename)

                        with open(filepath, "wb") as f:
                            f.write(image_data)

                        image_path = filepath.replace("\\", "/")

                    except Exception as e:
                        print("BASE64 ERROR :", e)
                        continue

                else:
                    image_path = image_url


                # first image main image
                if front_image == "":
                    front_image = image_path


                cur.execute("""
                    INSERT INTO product_images (
                        product_id,
                        type,
                        file_name,
                        label
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    product_id,
                    image_type,
                    image_path,
                    label
                ))


        # ---------- UPDATE FRONT IMAGE ----------
        if front_image:

            cur.execute("""
                UPDATE products
                SET image = ?
                WHERE id = ?
            """, (
                front_image,
                product_id
            ))


        con.commit()
        con.close()

        return redirect("/admin/dashboard")


    con.close()

    return render_template(
        "admin/add_product.html",
        categories=categories
    )