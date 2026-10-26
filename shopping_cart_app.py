"""
Online Shopping Cart - single file
OOP + Dictionaries + MySQL + Tkinter GUI

Setup:
    pip install mysql-connector-python
    Edit DB_CONFIG below (or set DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME env vars)
    python shopping_cart_app.py

The database, tables and sample products are created automatically on first run.
"""
import os
import tkinter as tk
from dataclasses import dataclass
from decimal import Decimal
from tkinter import messagebox, simpledialog, ttk

import mysql.connector

# ============================== CONFIG ==============================
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "Kremish"),
    "password": os.getenv("DB_PASSWORD", "Kremish@12402080601065"),      # <-- put your MySQL password here
}
DB_NAME = os.getenv("DB_NAME", "shop_db")
CURRENCY = "₹"

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS products (
        id       INT AUTO_INCREMENT PRIMARY KEY,
        name     VARCHAR(100)  NOT NULL,
        category VARCHAR(50)   NOT NULL,
        price    DECIMAL(10,2) NOT NULL CHECK (price >= 0),
        stock    INT           NOT NULL DEFAULT 0 CHECK (stock >= 0)
    )""",
    """CREATE TABLE IF NOT EXISTS orders (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        customer_name VARCHAR(100)  NOT NULL,
        total         DECIMAL(10,2) NOT NULL,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS order_items (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        order_id   INT           NOT NULL,
        product_id INT           NOT NULL,
        quantity   INT           NOT NULL,
        unit_price DECIMAL(10,2) NOT NULL,
        FOREIGN KEY (order_id)   REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )""",
]

SAMPLE_PRODUCTS = [
    ("Wireless Mouse", "Electronics", 699.00, 25),
    ("Mechanical Keyboard", "Electronics", 2499.00, 15),
    ("USB-C Charger 65W", "Electronics", 1299.00, 30),
    ("Bluetooth Speaker", "Electronics", 1799.00, 12),
    ("Cotton T-Shirt", "Clothing", 499.00, 50),
    ("Denim Jeans", "Clothing", 1499.00, 20),
    ("Running Shoes", "Clothing", 2999.00, 10),
    ("Python Crash Course", "Books", 899.00, 18),
    ("Clean Code", "Books", 999.00, 8),
    ("Notebook (Pack of 5)", "Stationery", 349.00, 40),
    ("Gel Pen Set", "Stationery", 199.00, 60),
]


# ============================== MODELS ==============================
@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category: str
    price: Decimal
    stock: int


class CartItem:
    def __init__(self, product: Product, quantity: int = 1):
        self.product = product
        self.quantity = quantity

    @property
    def subtotal(self) -> Decimal:
        return self.product.price * self.quantity


class Cart:
    """Dictionary-backed cart:  {product_id: CartItem}"""

    def __init__(self):
        self.items: dict[int, CartItem] = {}

    def add(self, product: Product, quantity: int = 1) -> None:
        if quantity < 1:
            raise ValueError("Quantity must be at least 1.")
        current = self.items[product.id].quantity if product.id in self.items else 0
        if current + quantity > product.stock:
            raise ValueError(
                f"Only {product.stock} of '{product.name}' in stock "
                f"({current} already in cart).")
        if product.id in self.items:
            self.items[product.id].quantity += quantity
        else:
            self.items[product.id] = CartItem(product, quantity)

    def set_quantity(self, product_id: int, quantity: int) -> None:
        item = self.items[product_id]
        if quantity < 1:
            self.remove(product_id)
            return
        if quantity > item.product.stock:
            raise ValueError(f"Only {item.product.stock} in stock.")
        item.quantity = quantity

    def remove(self, product_id: int) -> None:
        self.items.pop(product_id, None)

    def clear(self) -> None:
        self.items.clear()

    @property
    def total(self) -> Decimal:
        return sum((i.subtotal for i in self.items.values()), Decimal("0.00"))

    @property
    def count(self) -> int:
        return sum(i.quantity for i in self.items.values())

    def is_empty(self) -> bool:
        return not self.items


# ============================== DATABASE ==============================
class Database:
    def __init__(self):
        self._bootstrap()
        self.conn = mysql.connector.connect(database=DB_NAME, **DB_CONFIG)

    @staticmethod
    def _bootstrap():
        """Create database, tables and sample data if they don't exist yet."""
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
        cur.execute(f"USE `{DB_NAME}`")
        for stmt in SCHEMA:
            cur.execute(stmt)
        cur.execute("SELECT COUNT(*) FROM products")
        if cur.fetchone()[0] == 0:
            cur.executemany(
                "INSERT INTO products (name, category, price, stock) VALUES (%s, %s, %s, %s)",
                SAMPLE_PRODUCTS)
        conn.commit()
        cur.close()
        conn.close()

    def get_categories(self) -> list[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT category FROM products ORDER BY category")
        rows = [r[0] for r in cur.fetchall()]
        cur.close()
        return rows

    def get_products(self, search: str = "", category: str | None = None) -> list[Product]:
        sql = "SELECT id, name, category, price, stock FROM products WHERE name LIKE %s"
        params: list = [f"%{search}%"]
        if category:
            sql += " AND category = %s"
            params.append(category)
        sql += " ORDER BY name"
        cur = self.conn.cursor(dictionary=True)      # rows come back as dictionaries
        cur.execute(sql, params)
        products = [Product(**row) for row in cur.fetchall()]
        cur.close()
        return products

    def get_order_history(self, limit: int = 20) -> list[dict]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, customer_name, total, created_at FROM orders "
            "ORDER BY id DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
        cur.close()
        return rows

    def place_order(self, customer_name: str, cart: Cart) -> int:
        """Atomic checkout: stock check + stock update + order insert in one transaction."""
        cur = self.conn.cursor()
        try:
            self.conn.start_transaction()
            for item in cart.items.values():
                cur.execute(
                    "UPDATE products SET stock = stock - %s WHERE id = %s AND stock >= %s",
                    (item.quantity, item.product.id, item.quantity))
                if cur.rowcount == 0:
                    raise ValueError(f"'{item.product.name}' no longer has enough stock.")
            cur.execute(
                "INSERT INTO orders (customer_name, total) VALUES (%s, %s)",
                (customer_name, cart.total))
            order_id = cur.lastrowid
            cur.executemany(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                "VALUES (%s, %s, %s, %s)",
                [(order_id, i.product.id, i.quantity, i.product.price)
                 for i in cart.items.values()])
            self.conn.commit()
            return order_id
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def close(self) -> None:
        if self.conn.is_connected():
            self.conn.close()


# ============================== GUI ==============================
class ShopApp(tk.Tk):
    def __init__(self, db: Database):
        super().__init__()
        self.title("Online Shopping Cart")
        self.geometry("1100x620")
        self.minsize(900, 500)
        self.db = db
        self.cart = Cart()
        self.products: dict[int, Product] = {}      # id -> Product for quick lookup

        self._build_ui()
        self.refresh_products()
        self.refresh_cart()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=26)
        style.configure("Total.TLabel", font=("Segoe UI", 14, "bold"))

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # ---- left: product catalogue ----
        left = ttk.LabelFrame(paned, text="Products", padding=8)
        paned.add(left, weight=3)

        bar = ttk.Frame(left)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_products())
        ttk.Entry(bar, textvariable=self.search_var, width=22).pack(side="left", padx=6)
        ttk.Label(bar, text="Category:").pack(side="left", padx=(10, 0))
        self.category_var = tk.StringVar(value="All")
        self.category_box = ttk.Combobox(
            bar, textvariable=self.category_var, state="readonly", width=16,
            values=["All"] + self.db.get_categories())
        self.category_box.pack(side="left", padx=6)
        self.category_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_products())

        cols = ("name", "category", "price", "stock")
        self.product_tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for col, text, w in (("name", "Name", 220), ("category", "Category", 110),
                             ("price", "Price", 90), ("stock", "Stock", 60)):
            self.product_tree.heading(col, text=text)
            self.product_tree.column(col, width=w, anchor="w" if col in ("name", "category") else "e")
        self.product_tree.pack(fill="both", expand=True)
        self.product_tree.bind("<Double-1>", lambda _e: self.add_to_cart())

        add_bar = ttk.Frame(left)
        add_bar.pack(fill="x", pady=(8, 0))
        ttk.Label(add_bar, text="Qty:").pack(side="left")
        self.qty_var = tk.IntVar(value=1)
        ttk.Spinbox(add_bar, from_=1, to=99, textvariable=self.qty_var, width=5).pack(side="left", padx=6)
        ttk.Button(add_bar, text="Add to Cart  ➜", command=self.add_to_cart).pack(side="left", padx=6)

        # ---- right: cart ----
        right = ttk.LabelFrame(paned, text="Your Cart", padding=8)
        paned.add(right, weight=2)

        cols = ("name", "price", "qty", "subtotal")
        self.cart_tree = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        for col, text, w in (("name", "Item", 170), ("price", "Price", 80),
                             ("qty", "Qty", 45), ("subtotal", "Subtotal", 90)):
            self.cart_tree.heading(col, text=text)
            self.cart_tree.column(col, width=w, anchor="w" if col == "name" else "e")
        self.cart_tree.pack(fill="both", expand=True)

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="+", width=3, command=lambda: self.change_qty(+1)).pack(side="left")
        ttk.Button(btns, text="−", width=3, command=lambda: self.change_qty(-1)).pack(side="left", padx=4)
        ttk.Button(btns, text="Remove", command=self.remove_selected).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear", command=self.clear_cart).pack(side="left", padx=4)

        self.total_var = tk.StringVar()
        ttk.Label(right, textvariable=self.total_var, style="Total.TLabel").pack(anchor="e", pady=4)
        ttk.Button(right, text="Checkout", command=self.checkout).pack(fill="x", pady=2)
        ttk.Button(right, text="Order History", command=self.show_history).pack(fill="x", pady=2)

        self.status_var = tk.StringVar(value="Double-click a product to add it to the cart.")
        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    # ---- refresh ----
    def refresh_products(self):
        category = self.category_var.get()
        products = self.db.get_products(
            self.search_var.get().strip(), None if category == "All" else category)
        self.products = {p.id: p for p in products}
        self.product_tree.delete(*self.product_tree.get_children())
        for p in products:
            self.product_tree.insert("", "end", iid=str(p.id), values=(
                p.name, p.category, f"{CURRENCY}{p.price:,.2f}", p.stock))

    def refresh_cart(self):
        self.cart_tree.delete(*self.cart_tree.get_children())
        for pid, item in self.cart.items.items():
            self.cart_tree.insert("", "end", iid=str(pid), values=(
                item.product.name, f"{CURRENCY}{item.product.price:,.2f}",
                item.quantity, f"{CURRENCY}{item.subtotal:,.2f}"))
        self.total_var.set(f"Total ({self.cart.count} items): {CURRENCY}{self.cart.total:,.2f}")

    # ---- actions ----
    @staticmethod
    def _selected(tree):
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def add_to_cart(self):
        pid = self._selected(self.product_tree)
        if pid is None:
            return messagebox.showinfo("Select a product", "Please select a product first.")
        try:
            qty = int(self.qty_var.get())
            self.cart.add(self.products[pid], qty)
        except (ValueError, tk.TclError) as e:
            return messagebox.showwarning("Cannot add", str(e) or "Invalid quantity.")
        self.status_var.set(f"Added {qty} × {self.products[pid].name}")
        self.refresh_cart()

    def change_qty(self, delta):
        pid = self._selected(self.cart_tree)
        if pid is None:
            return
        try:
            self.cart.set_quantity(pid, self.cart.items[pid].quantity + delta)
        except ValueError as e:
            messagebox.showwarning("Stock limit", str(e))
        self.refresh_cart()

    def remove_selected(self):
        pid = self._selected(self.cart_tree)
        if pid is not None:
            self.cart.remove(pid)
            self.refresh_cart()

    def clear_cart(self):
        if not self.cart.is_empty() and messagebox.askyesno("Clear cart", "Remove all items?"):
            self.cart.clear()
            self.refresh_cart()

    def checkout(self):
        if self.cart.is_empty():
            return messagebox.showinfo("Cart empty", "Add some products first.")
        name = simpledialog.askstring("Checkout", "Customer name:", parent=self)
        if not name or not name.strip():
            return
        try:
            order_id = self.db.place_order(name.strip(), self.cart)
        except (ValueError, mysql.connector.Error) as e:
            messagebox.showerror("Order failed", str(e))
            self.refresh_products()
            return
        total = self.cart.total
        self.cart.clear()
        self.refresh_cart()
        self.refresh_products()
        self.status_var.set(f"Order #{order_id} placed.")
        messagebox.showinfo(
            "Order placed",
            f"Thank you, {name.strip()}!\nOrder #{order_id}\nTotal: {CURRENCY}{total:,.2f}")

    def show_history(self):
        win = tk.Toplevel(self)
        win.title("Order History")
        win.geometry("560x320")
        cols = ("id", "customer", "total", "date")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for col, text, w in (("id", "Order #", 70), ("customer", "Customer", 170),
                             ("total", "Total", 100), ("date", "Date", 170)):
            tree.heading(col, text=text)
            tree.column(col, width=w)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for o in self.db.get_order_history():
            tree.insert("", "end", values=(
                o["id"], o["customer_name"], f"{CURRENCY}{o['total']:,.2f}", o["created_at"]))

    def on_close(self):
        self.db.close()
        self.destroy()


# ============================== MAIN ==============================
if __name__ == "__main__":
    try:
        database = Database()
    except mysql.connector.Error as err:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Database connection failed",
            f"{err}\n\nCheck that MySQL is running and that the user/password in "
            "DB_CONFIG (or DB_USER / DB_PASSWORD env vars) are correct.")
        raise SystemExit(1)
    ShopApp(database).mainloop()
