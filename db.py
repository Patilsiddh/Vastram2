from flask import session

@app.route("/show_wishlist")
def show_wishlist():
    wishlist = session.get("wishlist", [])
    return str(wishlist)