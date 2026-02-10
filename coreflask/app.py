from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'annisa_ta'

# ================= DATABASE =================
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="db_restoran_annisa"
    )

# ================= REGISTER =================
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # cek username
        cursor.execute("SELECT * FROM pelanggan_annisa WHERE username=%s", (username,))
        if cursor.fetchone():
            flash('Username sudah ada!')
            conn.close()
            return redirect(url_for('register'))

        # insert user baru
        cursor.execute(
            "INSERT INTO pelanggan_annisa (username, password, role) VALUES (%s,%s,%s)",
            (username, password, role)
        )
        conn.commit()
        conn.close()
        flash('Registrasi berhasil! Silakan login.')
        return redirect(url_for('login'))

    return render_template('register.html')

# ================= LOGIN =================
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM pelanggan_annisa WHERE username=%s AND password=%s",
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session['role'] = user['role']
            if user['role'] == 'admin':
                session['username'] = user['username']
                return redirect(url_for('admin_dashboard'))
            else:
                session['id_pelanggan'] = user['id_user']
                return redirect(url_for('menu'))
        else:
            flash('Username atau password salah!')
            return redirect(url_for('login'))

    return render_template('login.html')

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================= ADMIN DASHBOARD =================
@app.route('/admin')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        flash('Silakan login sebagai admin!')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Data menu
    cursor.execute("SELECT * FROM menu")
    menu = cursor.fetchall()

    # Data pesanan
    cursor.execute("""
        SELECT p.id_pesanan, m.nama_menu, p.jumlah, p.total_harga, p.status_pesanan, pl.username
        FROM pesanan p
        JOIN menu m ON p.id_menu = m.id_menu
        JOIN pelanggan_annisa pl ON p.id_pelanggan = pl.id_user
        ORDER BY p.tanggal_pesanan DESC
    """)
    pesanan = cursor.fetchall()
    conn.close()

    return render_template('Dashbord_admin.html', menu=menu, pesanan=pesanan)

# ================= MENU PELANGGAN =================
@app.route('/menu')
def menu():
    if 'role' not in session or session['role'] != 'pelanggan':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM menu WHERE status='tersedia'")
    data_menu = cursor.fetchall()
    conn.close()
    return render_template('Dashbord.html', menu=data_menu)

# ================= DETAIL MENU =================
@app.route('/menu/<int:id_menu>')
def detail_menu(id_menu):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM menu WHERE id_menu=%s", (id_menu,))
    menu = cursor.fetchone()
    conn.close()

    if not menu:
        return "Menu tidak ditemukan", 404

    return render_template('detail_menu.html', menu=menu)

# ================= SIMPAN PESANAN =================
@app.route('/pesan', methods=['POST'])
def pesan_menu():
    id_pelanggan = session.get('id_pelanggan')
    if not id_pelanggan:
        flash('Silakan login terlebih dahulu untuk memesan!')
        return redirect(url_for('login'))

    id_menu = request.form['id_menu']
    jumlah = int(request.form['jumlah'])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT harga FROM menu WHERE id_menu=%s", (id_menu,))
    menu = cursor.fetchone()
    if not menu:
        conn.close()
        return "Menu tidak ditemukan", 404

    total = menu['harga'] * jumlah

    # cek apakah sudah ada pesanan yang diproses
    cursor.execute("""
        SELECT * FROM pesanan
        WHERE id_pelanggan=%s AND id_menu=%s AND status_pesanan='diproses'
    """, (id_pelanggan, id_menu))
    existing = cursor.fetchone()

    if existing:
        new_jumlah = existing['jumlah'] + jumlah
        new_total = existing['total_harga'] + total
        cursor.execute("""
            UPDATE pesanan
            SET jumlah=%s, total_harga=%s
            WHERE id_pesanan=%s
        """, (new_jumlah, new_total, existing['id_pesanan']))
    else:
        cursor.execute("""
            INSERT INTO pesanan
            (id_pelanggan, id_menu, jumlah, total_harga, status_pesanan, tanggal_pesanan)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_pelanggan, id_menu, jumlah, total, 'diproses', datetime.now()))

    conn.commit()
    conn.close()
    flash('Menu berhasil ditambahkan ke pesanan!')
    return redirect(url_for('pesanan'))

# ================= PESANAN PELANGGAN =================
@app.route('/pesanan')
def pesanan():
    id_pelanggan = session.get('id_pelanggan')
    if not id_pelanggan:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ambil semua pesanan dengan status diproses, selesai, dibatalkan
    cursor.execute("""
        SELECT p.id_pesanan, m.nama_menu, p.jumlah, p.total_harga, p.status_pesanan
        FROM pesanan p
        JOIN menu m ON p.id_menu = m.id_menu
        WHERE p.id_pelanggan=%s AND p.status_pesanan IN ('diproses', 'selesai', 'dibatalkan')
        ORDER BY p.tanggal_pesanan DESC
    """, (id_pelanggan,))
    data = cursor.fetchall()

    # hitung grand total
    cursor.execute("""
        SELECT SUM(total_harga) AS grand_total
        FROM pesanan
        WHERE id_pelanggan=%s AND status_pesanan IN ('diproses', 'selesai', 'dibatalkan')
    """, (id_pelanggan,))
    total = cursor.fetchone()
    conn.close()

    return render_template('pesanan_user.html', pesanan=data, grand_total=total['grand_total'] or 0)

# ================= KONFIRMASI PESANAN =================
@app.route('/konfirmasi', methods=['POST'])
def konfirmasi():
    id_pelanggan = session.get('id_pelanggan')
    if not id_pelanggan:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE pesanan
        SET status_pesanan='dikonfirmasi'
        WHERE id_pelanggan=%s AND status_pesanan='diproses'
    """, (id_pelanggan,))
    conn.commit()
    conn.close()
    return redirect(url_for('menu'))

# ================= EDIT MENU =================
@app.route('/menu/edit/<int:id_menu>', methods=['GET', 'POST'])
def edit_menu(id_menu):
    if 'role' not in session or session['role'] != 'admin':
        flash('Silakan login sebagai admin!')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nama_menu = request.form['nama_menu']
        harga = request.form['harga']
        status = request.form['status']
        cursor.execute("""
            UPDATE menu SET nama_menu=%s, harga=%s, status=%s WHERE id_menu=%s
        """, (nama_menu, harga, status, id_menu))
        conn.commit()
        conn.close()
        flash('Menu berhasil diupdate!')
        return redirect(url_for('admin_dashboard'))

    cursor.execute("SELECT * FROM menu WHERE id_menu=%s", (id_menu,))
    menu = cursor.fetchone()
    conn.close()
    return render_template('edit_menu.html', menu=menu)

# ================= HAPUS MENU =================
@app.route('/menu/hapus/<int:id_menu>')
def hapus_menu(id_menu):
    if 'role' not in session or session['role'] != 'admin':
        flash('Silakan login sebagai admin!')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menu WHERE id_menu=%s", (id_menu,))
    conn.commit()
    conn.close()
    flash('Menu berhasil dihapus!')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
