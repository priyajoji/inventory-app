"""Department Inventory Management System (Streamlit + SQLite).

Data lives in a SQLite file under DATA_DIR (default ./data). In the container,
DATA_DIR=/data is backed by a Podman named volume, so records survive
container removal and recreation.
"""

import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "inventory.db"
DEFAULT_THRESHOLD = int(os.environ.get("LOW_STOCK_THRESHOLD", "10"))


# ---------- database layer ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity >= 0),
                archived INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_item(code, name, quantity):
    code, name = code.strip().upper(), name.strip()
    if not code or not name:
        return False, "Name and code are required."
    try:
        with closing(get_conn()) as conn, conn:
            conn.execute(
                "INSERT INTO items (code, name, quantity, updated_at) VALUES (?, ?, ?, ?)",
                (code, name, int(quantity), now()),
            )
        return True, f"Added {name} ({code})."
    except sqlite3.IntegrityError:
        return False, f"Item code '{code}' already exists (it may be archived)."


def set_quantity(code, quantity):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "UPDATE items SET quantity = ?, updated_at = ? WHERE code = ?",
            (int(quantity), now(), code),
        )


def set_archived(code, archived):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "UPDATE items SET archived = ?, updated_at = ? WHERE code = ?",
            (1 if archived else 0, now(), code),
        )


def fetch_items(search="", archived=False):
    like = f"%{search.strip()}%"
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT code, name, quantity, updated_at FROM items
            WHERE archived = ? AND (code LIKE ? OR name LIKE ?)
            ORDER BY name COLLATE NOCASE
            """,
            (1 if archived else 0, like, like),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows], columns=["code", "name", "quantity", "updated_at"])


# ---------- UI ----------
st.set_page_config(page_title="Inventory Manager", page_icon="📦", layout="wide")
init_db()

st.title("📦 Department Inventory Manager")

with st.sidebar:
    st.header("Settings")
    threshold = st.number_input(
        "Low-stock threshold",
        min_value=0,
        value=DEFAULT_THRESHOLD,
        step=1,
        help="Items with quantity at or below this value are flagged as low stock.",
    )
    st.caption(f"Database: `{DB_PATH}`")

flash = st.session_state.pop("flash", None)
if flash:
    (st.success if flash[0] else st.error)(flash[1])

active = fetch_items()
low = active[active["quantity"] <= threshold]

m1, m2, m3 = st.columns(3)
m1.metric("Active items", len(active))
m2.metric("Total units", int(active["quantity"].sum()) if len(active) else 0)
m3.metric("Low-stock items", len(low))

if len(low):
    names = ", ".join(f"{r.name} ({r.quantity})" for r in low.itertuples())
    st.warning(f"⚠️ **Low stock** (threshold ≤ {threshold}): {names}")

tab_stock, tab_add, tab_update, tab_archive = st.tabs(
    ["Current stock", "Add item", "Update quantity", "Archive / restore"]
)

with tab_stock:
    search = st.text_input("Search by name or code", placeholder="e.g. toner, USB, HDMI-01")
    df = fetch_items(search)
    if df.empty:
        st.info("No matching items.")
    else:
        df = df.copy()
        df["status"] = df["quantity"].apply(lambda q: "⚠️ LOW" if q <= threshold else "OK")

        def highlight(row):
            color = "background-color: #7F00FF" if row["status"] != "OK" else ""
            return [color] * len(row)

        st.dataframe(df.style.apply(highlight, axis=1), width="stretch", hide_index=True)

with tab_add:
    with st.form("add_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        name = c1.text_input("Item name")
        code = c2.text_input("Item code")
        qty = c3.number_input("Quantity", min_value=0, value=0, step=1)
        if st.form_submit_button("Add item"):
            st.session_state["flash"] = add_item(code, name, qty)
            st.rerun()

with tab_update:
    if active.empty:
        st.info("No active items to update.")
    else:
        options = {f"{r.code} - {r.name} (qty {r.quantity})": r.code for r in active.itertuples()}
        label = st.selectbox("Select item", list(options))
        sel = options[label]
        current = int(active.loc[active["code"] == sel, "quantity"].iloc[0])
        mode = st.radio("Method", ["Set exact quantity", "Add / remove stock"], horizontal=True)
        if mode == "Set exact quantity":
            new_qty = st.number_input("New quantity", min_value=0, value=current, step=1)
        else:
            delta = st.number_input("Change (+ receive / − issue)", value=0, step=1)
            new_qty = current + delta
            st.caption(f"Resulting quantity: **{new_qty}**")
        if st.button("Update quantity"):
            if new_qty < 0:
                st.session_state["flash"] = (False, "Quantity cannot go below zero.")
            else:
                set_quantity(sel, new_qty)
                st.session_state["flash"] = (True, f"{sel} updated to {new_qty}.")
            st.rerun()

with tab_archive:
    left, right = st.columns(2)
    with left:
        st.subheader("Archive an item")
        if active.empty:
            st.info("Nothing to archive.")
        else:
            a_opts = {f"{r.code} - {r.name}": r.code for r in active.itertuples()}
            a_label = st.selectbox("Active item", list(a_opts), key="arch_sel")
            if st.button("Archive"):
                set_archived(a_opts[a_label], True)
                st.session_state["flash"] = (True, f"Archived {a_opts[a_label]}.")
                st.rerun()
    with right:
        st.subheader("Archived items")
        archived = fetch_items(archived=True)
        if archived.empty:
            st.info("No archived items.")
        else:
            st.dataframe(archived, width="stretch", hide_index=True)
            r_opts = {f"{r.code} - {r.name}": r.code for r in archived.itertuples()}
            r_label = st.selectbox("Restore item", list(r_opts), key="rest_sel")
            if st.button("Restore"):
                set_archived(r_opts[r_label], False)
                st.session_state["flash"] = (True, f"Restored {r_opts[r_label]}.")
                st.rerun()
