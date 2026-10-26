# Online Shopping Cart (Python · OOP · MySQL · Tkinter)

## Setup
1. Install Python 3.10+ and MySQL Server.
2. `pip install -r requirements.txt`
3. Create the database and sample products:
   `mysql -u root -p < schema.sql`
4. Set your MySQL credentials (defaults: host `localhost`, user `root`, empty password, db `shop_db`):
   - Windows (cmd): `set DB_USER=root` / `set DB_PASSWORD=yourpassword`
   - Mac/Linux: `export DB_USER=root DB_PASSWORD=yourpassword`
5. Run: `python gui.py`

## Files
- `models.py`   – `Product`, `CartItem`, `Cart` classes (cart items kept in a dict `{product_id: CartItem}`)
- `database.py` – `Database` class: queries, atomic checkout transaction (stock check + order insert)
- `gui.py`      – Tkinter interface: search/filter, add to cart, change qty, remove, checkout, order history
- `schema.sql`  – tables + sample data

## Features
Search and category filter · double-click to add · +/− quantity · stock validation ·
checkout saves order and order items and reduces stock in one transaction · order history window.
