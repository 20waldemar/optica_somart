import streamlit as st
import bcrypt
import pandas as pd
import os
from io import BytesIO
from database import get_connection
from datetime import datetime, date
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

IMAGENES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "productos")
os.makedirs(IMAGENES_DIR, exist_ok=True)

OPTICA_CONFIG = {
    'nombre': 'OPTICA SOTMART',
    'doctor': 'Dra Evelyn SOTMART',
    'subtitulo': 'CENTRO ESPECIALIZADO',
    'direccion': 'Av. Principal, C.C. Plaza, Local 5, Valencia',
    'telefono': '0412-154-125',
}

st.set_page_config(page_title="Óptica SOTMART", page_icon="👓", layout="wide", initial_sidebar_state="expanded")

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_data' not in st.session_state: st.session_state.user_data = None
if 'page' not in st.session_state: st.session_state.page = "Opciones o Tablero"
if 'form_counter' not in st.session_state: st.session_state.form_counter = 0
if 'consulta_id' not in st.session_state: st.session_state.consulta_id = None

# ═══════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════
def verificar_login(username, password):
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT id, username, password_hash, nombre_completo, email, rol FROM usuarios WHERE username = %s AND activo = TRUE", (username,))
        user = cursor.fetchone(); cursor.close(); conn.close()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
            return {'id': user[0], 'username': user[1], 'nombre': user[3], 'email': user[4], 'rol': user[5]}
        return None
    except Exception as e:
        st.error(f"Error: {e}"); return None

def actualizar_password_admin():
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM usuarios WHERE username = 'admin'")
        result = cursor.fetchone()
        if result and result[0] == 'pendiente_de_actualizar':
            hashed = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("UPDATE usuarios SET password_hash = %s WHERE username = 'admin'", (hashed,))
            conn.commit(); st.success("✅ Contraseña de admin actualizada. Usuario: admin / Contraseña: admin123")
        cursor.close(); conn.close()
    except Exception:
        pass

def verificar_paciente_con_historial(paciente_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM examenes WHERE paciente_id = %s", (paciente_id,)); examenes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ordenes WHERE paciente_id = %s", (paciente_id,)); ordenes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM pagos WHERE paciente_id = %s", (paciente_id,)); pagos = cursor.fetchone()[0]
    cursor.close(); conn.close()
    return {'examenes': examenes, 'ordenes': ordenes, 'pagos': pagos, 'tiene_historial': examenes > 0 or ordenes > 0 or pagos > 0}

def buscar_paciente_por_cedula(cedula):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nombre, apellidos, cedula, fecha_nacimiento, telefono, email, direccion, whatsapp, notas,
               es_menor, representante_id, parentesco, estado_id, municipio_id, ciudad_id, sexo, usa_lentes, empresa
        FROM pacientes WHERE cedula ILIKE %s
    """, (f'%{cedula}%',))
    paciente = cursor.fetchone(); cursor.close(); conn.close()
    return paciente

def calcular_edad(fecha_nacimiento):
    if fecha_nacimiento is None: return None
    today = date.today()
    return today.year - fecha_nacimiento.year - ((today.month, today.day) < (fecha_nacimiento.month, fecha_nacimiento.day))

def fmt_num(v):
    if v is None: return ""
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(f)
    except Exception:
        return str(v)

def generar_pdf_orden(d):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    st_cent = ParagraphStyle('cent', parent=styles['Normal'], alignment=TA_CENTER)
    elementos = []
    tbl_head = Table([[
        Paragraph(f"<b>{d['optica']}</b>", styles['Normal']),
        Paragraph(f"<font color='#1F6FB2'><b>{d['doctor']}</b></font><br/>{d['subtitulo']}<br/>{d['direccion']}<br/>Teléfono: {d['telefono']}", st_cent),
        Paragraph(f"<font color='red'><b>ORDEN</b><br/><b>N°-{d['numero']}</b></font>", styles['Normal']),
    ]], colWidths=[5*cm, 8*cm, 4*cm])
    tbl_head.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (2,0), (2,0), 'RIGHT'), ('BOTTOMPADDING', (0,0), (-1,-1), 10)]))
    elementos.append(tbl_head)
    info = Table([[
        Paragraph(f"<b>Fecha:</b> {d['fecha']}", styles['Normal']),
        Paragraph(f"<b>Paciente:</b> {d['paciente']}", styles['Normal']),
        Paragraph(f"<b>Edad:</b> {d['edad']}", styles['Normal']),
        Paragraph(f"<b>Cédula:</b> {d['cedula']}", styles['Normal']),
    ]], colWidths=[4*cm, 6*cm, 3*cm, 4*cm])
    info.setStyle(TableStyle([('BOTTOMPADDING', (0,0), (-1,-1), 8)]))
    elementos.append(info)
    rx_data = [
        ['Ojo', 'Esfera', 'Cilindro', 'Eje', 'Prisma', 'AV Lejos', 'AV Cerca', 'ADD', 'Tipo de Lente'],
        ['OD', d['rx_od_esf'], d['rx_od_cil'], d['rx_od_eje'], d['rx_od_prisma'], d['rx_od_avl'], d['rx_od_avc'], d['rx_od_add'], d['rx_od_tipo']],
        ['OI', d['rx_oi_esf'], d['rx_oi_cil'], d['rx_oi_eje'], d['rx_oi_prisma'], d['rx_oi_avl'], d['rx_oi_avc'], d['rx_oi_add'], d['rx_oi_tipo']],
    ]
    tbl_rx = Table(rx_data, colWidths=[1.4*cm, 1.9*cm, 1.9*cm, 1.5*cm, 1.9*cm, 2.1*cm, 2.1*cm, 1.5*cm, 3.7*cm])
    tbl_rx.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.7, colors.HexColor('#2E9BD6')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#EAF6FC')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elementos.append(Paragraph("<b>Rx Final</b>", styles['Normal'])); elementos.append(Spacer(1, 0.2*cm)); elementos.append(tbl_rx); elementos.append(Spacer(1, 0.6*cm))
    left = [Paragraph("<b>Lente y Materiales</b>", styles['Normal']), Spacer(1, 0.2*cm),
            Paragraph(f"<b>Tipo de lente:</b> {d['tipo_lente'] or '—'}", styles['Normal']), Spacer(1, 0.15*cm),
            Paragraph(f"<b>Material del lente:</b> {d['material'] or '—'}", styles['Normal']), Spacer(1, 0.15*cm),
            Paragraph(f"<b>Tratamiento:</b> {d['tratamiento'] or '—'}", styles['Normal']), Spacer(1, 0.15*cm),
            Paragraph(f"<b>Detalles Adicionales:</b> {d['detalles'] or '—'}", styles['Normal'])]
    right = [Paragraph("<b>Laboratorio</b>", styles['Normal']), Spacer(1, 0.2*cm),
             Paragraph(f"<b>Laboratorio:</b> {d['laboratorio'] or '—'}", styles['Normal']), Spacer(1, 0.15*cm),
             Paragraph(f"<b>Fecha de Pedido:</b> {d['fecha_pedido']}", styles['Normal']), Spacer(1, 0.15*cm),
             Paragraph(f"<b>Fecha requerida:</b> {d['fecha_requerida']}", styles['Normal']), Spacer(1, 0.15*cm),
             Paragraph(f"<b>Hora requerida:</b> {d['hora_requerida']}", styles['Normal']), Spacer(1, 0.15*cm),
             Paragraph(f"<b>Hora de Pedido:</b> {d['hora']}", styles['Normal'])]
    tbl_cols = Table([[left, right]], colWidths=[9*cm, 8*cm])
    tbl_cols.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elementos.append(tbl_cols); elementos.append(Spacer(1, 1.2*cm))
    elementos.append(Paragraph("____________________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;____________________________", st_cent))
    elementos.append(Paragraph("Firma del Optómetra&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Sello del Laboratorio", st_cent))
    doc.build(elementos)
    pdf_bytes = buffer.getvalue(); buffer.close()
    return pdf_bytes
# ═══════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.title("👓 ÓpticaVision Pro")
    st.markdown("### Iniciar Sesión")
    actualizar_password_admin()
    with st.form("login_form"):
        username = st.text_input("👤 Usuario", placeholder="admin")
        password = st.text_input("🔒 Contraseña", type="password")
        if st.form_submit_button("🔐 Ingresar", use_container_width=True):
            if username and password:
                user_data = verificar_login(username, password)
                if user_data:
                    st.session_state.logged_in = True; st.session_state.user_data = user_data
                    st.success(f"¡Bienvenido, {user_data['nombre']}!"); st.balloons(); st.rerun()
                else: st.error("❌ Usuario o contraseña incorrectos")
            else: st.warning("⚠️ Ingresa usuario y contraseña")
    st.markdown("---")
    st.info("🔑 **Credenciales por defecto:** Usuario `admin` / Contraseña `admin123`")
# ═══════════════════════════════════════════════════════════
# SISTEMA PRINCIPAL
# ═══════════════════════════════════════════════════════════
else:
    with st.sidebar:
        st.title(" Óptica SOTMART")
        st.markdown(f"**Usuario:** {st.session_state.user_data['nombre']}")
        st.markdown(f"**Rol:** {st.session_state.user_data['rol']}")
        st.markdown("---")
        if st.button("🏠 Opciones o Tablero", use_container_width=True, type="primary" if st.session_state.page == "Opciones o Tablero" else "secondary"):
            st.session_state.page = "Opciones o Tablero"; st.rerun()
        if st.button("👤 Pacientes", use_container_width=True, type="primary" if st.session_state.page == "pacientes" else "secondary"):
            st.session_state.page = "pacientes"; st.rerun()
        if st.button("🔬 Exámenes", use_container_width=True, type="primary" if st.session_state.page == "examenes" else "secondary"):
            st.session_state.page = "examenes"; st.rerun()
        if st.button("🩺 Consultas", use_container_width=True, type="primary" if st.session_state.page == "consultas" else "secondary"):
            st.session_state.page = "consultas"; st.rerun()
        if st.button(" Pedidos", use_container_width=True, type="primary" if st.session_state.page == "pedidos" else "secondary"):
            st.session_state.page = "pedidos"; st.rerun()
        if st.button(" Inventario", use_container_width=True, type="primary" if st.session_state.page == "inventario" else "secondary"):
            st.session_state.page = "inventario"; st.rerun()
        if st.button("🛒 Compras", use_container_width=True, type="primary" if st.session_state.page == "compras" else "secondary"):
            st.session_state.page = "compras"; st.rerun()
        if st.button("🚚 Proveedores", use_container_width=True, type="primary" if st.session_state.page == "proveedores" else "secondary"):
            st.session_state.page = "proveedores"; st.rerun()
        if st.button("⚙️ Catálogos", use_container_width=True, type="primary" if st.session_state.page == "catalogos" else "secondary"):
            st.session_state.page = "catalogos"; st.rerun()
        if st.button("💰 Ventas", use_container_width=True, type="primary" if st.session_state.page == "ventas" else "secondary"):
            st.session_state.page = "ventas"; st.rerun()
        if st.button("📊 Cartera", use_container_width=True, type="primary" if st.session_state.page == "cartera" else "secondary"):
            st.session_state.page = "cartera"; st.rerun()
        st.markdown("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False; st.session_state.user_data = None; st.session_state.page = "Opciones o Tablero"; st.rerun()

    # ═════════════════════════════════════════════════════
    # Opciones o Tablero
    # ═══════════════════════════════════════════════════════
    if st.session_state.page == "Opciones o Tablero":
        st.title("🏠 Opciones o Tablero")
        st.markdown("### Bienvenido al Sistema de Gestión de Óptica")
        try:
            conn = get_connection(); conn.close(); st.success("✅ Conectado a la base de datos")
        except Exception as e:
            st.error(f" Error de conexión: {e}"); st.stop()
        conn = get_connection(); cursor = conn.cursor()
        col1, col2, col3, col4 = st.columns(4)
        cursor.execute("SELECT COUNT(*) FROM pacientes"); col1.metric(" Pacientes", cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM examenes"); col2.metric("🔬 Exámenes", cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM consultas"); col3.metric("🩺 Consultas", cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM productos WHERE activo = TRUE"); col4.metric(" Productos", cursor.fetchone()[0])
        cursor.close(); conn.close()

    # ═══════════════════════════════════════════════════════
    # PACIENTES
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "pacientes":
        st.title("👤 Gestión de Pacientes")
        tab1, tab2, tab3 = st.tabs(["➕ Nuevo Paciente", " Listado", " Buscar"])
        with tab1:
            st.subheader("Registrar Nuevo Paciente")
            if st.button(" Limpiar Formulario", key="limpiar_form_btn"):
                st.session_state.form_counter += 1
                if 'representante_id' in st.session_state: del st.session_state.representante_id
                if 'paciente_encontrado' in st.session_state: del st.session_state.paciente_encontrado
                st.rerun()
            es_menor = st.checkbox("👶 El paciente es menor de edad (requiere representante)", key=f"es_menor_{st.session_state.form_counter}")
            if es_menor:
                st.info("💡 **Primero debemos registrar al representante (padre/tutor)**")
                conn = get_connection()
                representantes = pd.read_sql("SELECT id, nombre, apellidos, cedula FROM pacientes WHERE es_menor = FALSE ORDER BY apellidos, nombre", conn)
                conn.close()
                if not representantes.empty:
                    representante_opciones = ["➕ Registrar nuevo representante"] + [f"{row['apellidos']} {row['nombre']} (V-{row['cedula'] or 'N/A'})" for _, row in representantes.iterrows()]
                    representante_seleccion = st.selectbox("Selecciona el representante o registra uno nuevo:", representante_opciones, key=f"rep_select_{st.session_state.form_counter}")
                    if representante_seleccion == " Registrar nuevo representante":
                        with st.form(f"nuevo_representante_{st.session_state.form_counter}"):
                            st.markdown("####  Datos del Representante")
                            col1, col2 = st.columns(2)
                            with col1:
                                rep_nombre = st.text_input("Nombre(s) *", key=f"rep_nom_{st.session_state.form_counter}")
                                rep_cedula = st.text_input("Cédula (V-12345678) *", key=f"rep_ced_{st.session_state.form_counter}")
                                rep_telefono = st.text_input("Teléfono", key=f"rep_tel_{st.session_state.form_counter}")
                            with col2:
                                rep_apellidos = st.text_input("Apellidos *", key=f"rep_ape_{st.session_state.form_counter}")
                                rep_email = st.text_input("Email", key=f"rep_email_{st.session_state.form_counter}")
                                rep_whatsapp = st.text_input("WhatsApp", key=f"rep_wa_{st.session_state.form_counter}")
                            rep_direccion = st.text_area("Dirección", key=f"rep_dir_{st.session_state.form_counter}")
                            if st.form_submit_button("💾 Guardar Representante", use_container_width=True):
                                if rep_nombre and rep_apellidos and rep_cedula:
                                    try:
                                        conn = get_connection(); cursor = conn.cursor()
                                        cursor.execute("INSERT INTO pacientes (nombre, apellidos, cedula, telefono, email, whatsapp, direccion, es_menor) VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE) RETURNING id",
                                                       (rep_nombre, rep_apellidos, rep_cedula, rep_telefono, rep_email, rep_whatsapp, rep_direccion))
                                        rep_id = cursor.fetchone()[0]; conn.commit(); cursor.close(); conn.close()
                                        st.success(f"✅ Representante **{rep_nombre} {rep_apellidos}** registrado")
                                        st.session_state.representante_id = rep_id; st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Ya existe un paciente con la cédula {rep_cedula}" if 'uq_pacientes_cedula' in str(e) else f" Error: {e}")
                                else: st.error("⚠️ Nombre, apellidos y cédula son obligatorios")
                    else:
                        rep_id = int(representantes.iloc[representante_opciones.index(representante_seleccion) - 1]['id'])
                        st.session_state.representante_id = rep_id
                        st.success(f"✅ Representante seleccionado: {representante_seleccion}")
                else: st.warning("No hay representantes registrados. Primero registra un representante.")
            st.markdown("---")
            st.markdown("### 🔍 Búsqueda Rápida por Cédula")
            col_cedula1, col_cedula2 = st.columns([3, 1])
            with col_cedula1:
                cedula_busqueda = st.text_input("Cédula a buscar:", placeholder="Ej: 12345678", key=f"cedula_busq_{st.session_state.form_counter}")
            with col_cedula2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔍 Buscar", use_container_width=True, key=f"btn_buscar_ced_{st.session_state.form_counter}"):
                    if cedula_busqueda:
                        paciente_encontrado = buscar_paciente_por_cedula(cedula_busqueda)
                        if paciente_encontrado:
                            st.session_state.paciente_encontrado = paciente_encontrado; st.rerun()
                        else:
                            st.session_state.paciente_encontrado = None
                            st.info(f"ℹ️ No existe paciente con cédula {cedula_busqueda}. Puedes registrarlo abajo.")
                    else: st.warning("⚠️ Ingresa una cédula para buscar")
            if 'paciente_encontrado' in st.session_state and st.session_state.paciente_encontrado:
                paciente = st.session_state.paciente_encontrado
                st.success(f"✅ Paciente encontrado: **{paciente[1]} {paciente[2]}** (Edad: {calcular_edad(paciente[4])} años)")
                col_ver, col_edit = st.columns(2)
                with col_ver:
                    if st.button("👁️ Ver Datos Completos", use_container_width=True, key=f"btn_ver_{paciente[0]}"):
                        st.session_state.ver_paciente_id = paciente[0]; st.session_state.page = "ver_paciente"; st.rerun()
                with col_edit:
                    if st.button("️ Editar Paciente", use_container_width=True, key=f"btn_edit_{paciente[0]}"):
                        st.session_state.editar_paciente_id = paciente[0]; st.session_state.page = "editar_paciente"; st.rerun()
                st.markdown("---")
            st.markdown("### 📝 Datos del Paciente")
            with st.form(f"nuevo_paciente_{st.session_state.form_counter}"):
                col1, col2 = st.columns(2)
                with col1: cedula = st.text_input("Cédula (V-12345678)", key=f"pac_ced_{st.session_state.form_counter}")
                with col2:
                    fecha_nac = st.date_input(
                        "Fecha de Nacimiento (DD/MM/AAAA)",
                        value=None,
                        min_value=date(1900, 1, 1),
                        max_value=date.today(),
                        format="DD/MM/YYYY",
                        key=f"pac_fn_{st.session_state.form_counter}"
                    )
                if fecha_nac: st.info(f"🎂 Edad calculada: **{calcular_edad(fecha_nac)} años**")
                col1, col2 = st.columns(2)
                with col1: nombre = st.text_input("Nombre(s) *", key=f"pac_nom_{st.session_state.form_counter}")
                with col2: apellidos = st.text_input("Apellidos *", key=f"pac_ape_{st.session_state.form_counter}")
                col1, col2 = st.columns(2)
                with col1: sexo = st.selectbox("Sexo", ["Seleccionar...", "Femenino", "Masculino"], key=f"pac_sexo_{st.session_state.form_counter}")
                with col2: usa_lentes = st.selectbox("¿Usa lentes?", ["Seleccionar...", "Sí", "No"], key=f"pac_lentes_{st.session_state.form_counter}")
                col1, col2 = st.columns(2)
                with col1: telefono = st.text_input("Teléfono (0412-1234567)", key=f"pac_tel_{st.session_state.form_counter}")
                with col2: whatsapp = st.text_input("WhatsApp", key=f"pac_wa_{st.session_state.form_counter}")
                email = st.text_input("Email", key=f"pac_email_{st.session_state.form_counter}")
                empresa = st.text_input("🏢 Empresa (opcional)", key=f"pac_empresa_{st.session_state.form_counter}")
                conn = get_connection()
                estados_df = pd.read_sql("SELECT id, nombre FROM estados ORDER BY nombre", conn); conn.close()
                estado_sel = st.selectbox("🇻🇪 Estado", ["Seleccionar..."] + estados_df['nombre'].tolist(), key=f"pac_est_{st.session_state.form_counter}")
                municipio_sel = "Seleccionar..."; ciudad_sel = "Seleccionar..."
                municipios_df = pd.DataFrame(); ciudades_df = pd.DataFrame()
                if estado_sel != "Seleccionar...":
                    estado_id_tmp = int(estados_df[estados_df['nombre'] == estado_sel]['id'].values[0])
                    conn = get_connection()
                    municipios_df = pd.read_sql("SELECT id, nombre FROM municipios WHERE estado_id = %s ORDER BY nombre", conn, params=(estado_id_tmp,)); conn.close()
                    if not municipios_df.empty:
                        municipio_sel = st.selectbox("🏘️ Municipio", ["Seleccionar..."] + municipios_df['nombre'].tolist(), key=f"pac_mun_{st.session_state.form_counter}")
                        if municipio_sel != "Seleccionar...":
                            mun_id_tmp = int(municipios_df[municipios_df['nombre'] == municipio_sel]['id'].values[0])
                            conn = get_connection()
                            ciudades_df = pd.read_sql("SELECT id, nombre, codigo_postal FROM ciudades WHERE municipio_id = %s ORDER BY nombre", conn, params=(mun_id_tmp,)); conn.close()
                            if not ciudades_df.empty:
                                ciudad_sel = st.selectbox("🏙️ Ciudad/Parroquia", ["Seleccionar..."] + ciudades_df['nombre'].tolist(), key=f"pac_ciu_{st.session_state.form_counter}")
                    else: st.info(f"ℹ️ No hay municipios registrados para {estado_sel}.")
                direccion = st.text_area(" Dirección (calle, número, urbanización)", key=f"pac_dir_{st.session_state.form_counter}")
                notas = st.text_area("📝 Notas adicionales", key=f"pac_notas_{st.session_state.form_counter}")
                parentesco = ""
                if es_menor:
                    parentesco = st.selectbox("👨‍ Parentesco con el representante", ["Padre", "Madre", "Tutor Legal", "Abuelo(a)", "Tío(a)", "Hermano(a) Mayor", "Otro"], key=f"pac_par_{st.session_state.form_counter}")
                if st.form_submit_button("💾 Guardar Paciente", use_container_width=True, type="primary"):
                    if nombre and apellidos:
                        try:
                            estado_id = municipio_id = ciudad_id = None
                            if estado_sel != "Seleccionar...":
                                estado_id = int(estados_df[estados_df['nombre'] == estado_sel]['id'].values[0])
                                if municipio_sel != "Seleccionar..." and not municipios_df.empty:
                                    municipio_id = int(municipios_df[municipios_df['nombre'] == municipio_sel]['id'].values[0])
                                    if ciudad_sel != "Seleccionar..." and not ciudades_df.empty:
                                        ciudad_id = int(ciudades_df[ciudades_df['nombre'] == ciudad_sel]['id'].values[0])
                            sexo_db = "F" if sexo == "Femenino" else "M" if sexo == "Masculino" else None
                            usa_lentes_db = True if usa_lentes == "Sí" else False if usa_lentes == "No" else None
                            conn = get_connection(); cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO pacientes (nombre, apellidos, cedula, fecha_nacimiento, telefono, email, direccion, whatsapp, notas,
                                es_menor, representante_id, parentesco, estado_id, municipio_id, ciudad_id, sexo, usa_lentes, empresa)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                            """, (nombre, apellidos, cedula if cedula else None, fecha_nac, telefono, email, direccion, whatsapp, notas, es_menor,
                                  st.session_state.get('representante_id'), parentesco if es_menor else None, estado_id, municipio_id, ciudad_id,
                                  sexo_db, usa_lentes_db, empresa if empresa else None))
                            paciente_id = cursor.fetchone()[0]; conn.commit(); cursor.close(); conn.close()
                            st.success(f"✅ Paciente **{nombre} {apellidos}** registrado (ID: {paciente_id})"); st.balloons()
                            st.session_state.form_counter += 1
                            if 'representante_id' in st.session_state: del st.session_state.representante_id
                            if 'paciente_encontrado' in st.session_state: del st.session_state.paciente_encontrado
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Ya existe un paciente con la cédula **{cedula}**." if 'uq_pacientes_cedula' in str(e) else f"❌ Error al registrar: {e}")
                    else: st.error("⚠️ Nombre y Apellidos son obligatorios")
        with tab2:
            st.subheader("📋 Listado de Pacientes")
            conn = get_connection()
            df = pd.read_sql("SELECT * FROM v_pacientes_completo ORDER BY apellidos, nombre", conn); conn.close()
            if not df.empty:
                df['fecha_nacimiento'] = pd.to_datetime(df['fecha_nacimiento']).dt.strftime('%d/%m/%Y')
                df['fecha_registro'] = pd.to_datetime(df['fecha_registro']).dt.strftime('%d/%m/%Y')
                df['sexo'] = df['sexo'].map({'F': 'Femenino', 'M': 'Masculino'}).fillna('No especificado')
                df['usa_lentes'] = df['usa_lentes'].map({True: 'Sí', False: 'No', None: 'No especificado'})
                st.dataframe(df, use_container_width=True, height=400)
                col1, col2, col3 = st.columns(3)
                with col1: st.metric("👥 Total Pacientes", len(df))
                with col2: st.metric("👶 Menores de Edad", len(df[df['es_menor'] == True]))
                with col3: st.metric("🧑 Adultos", len(df[df['es_menor'] == False]))
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(label=" Exportar a CSV", data=csv, file_name='pacientes.csv', mime='text/csv', use_container_width=True)
                st.markdown("---")
                st.subheader("🗑️ Eliminar Paciente")
                paciente_a_eliminar = st.selectbox("Selecciona el paciente a eliminar:", [f"{row['apellidos']} {row['nombre']} (Cédula: {row['cedula'] or 'N/A'})" for _, row in df.iterrows()], key="select_eliminar")
                if paciente_a_eliminar and st.button("️ Verificar y Eliminar", use_container_width=True, key="btn_verificar_eliminar"):
                    paciente_id = int(df[df['apellidos'] + ' ' + df['nombre'] == paciente_a_eliminar.split(' (Cédula:')[0].strip()]['id'].values[0])
                    historial = verificar_paciente_con_historial(paciente_id)
                    if historial['tiene_historial']:
                        st.error("❌ **No se puede eliminar**: tiene historial clínico.")
                        if historial['examenes'] > 0: st.warning(f"   - {historial['examenes']} examen(es)")
                        if historial['ordenes'] > 0: st.warning(f"   - {historial['ordenes']} orden(es)")
                        if historial['pagos'] > 0: st.warning(f"   - {historial['pagos']} pago(s)")
                    else:
                        st.warning(f"⚠️ ¿Seguro de eliminar a **{paciente_a_eliminar.split(' (')[0]}**?")
                        col_conf, col_can = st.columns(2)
                        with col_conf:
                            if st.button("✅ Sí, eliminar", use_container_width=True, key="confirmar_eliminar"):
                                try:
                                    conn = get_connection(); cursor = conn.cursor()
                                    cursor.execute("DELETE FROM pacientes WHERE id = %s", (paciente_id,))
                                    conn.commit(); cursor.close(); conn.close()
                                    st.success("✅ Paciente eliminado correctamente"); st.rerun()
                                except Exception as e: st.error(f"❌ Error al eliminar: {e}")
                        with col_can:
                            if st.button(" Cancelar", use_container_width=True, key="cancelar_eliminar"): st.rerun()
            else: st.info("📭 No hay pacientes registrados aún.")
        with tab3:
            st.subheader("🔍 Buscar Paciente")
            st.info("💡 **Haz click en cualquier fila de la tabla para seleccionar el paciente**")
            busqueda = st.text_input("🔎 Filtrar por cédula, nombre, apellido o teléfono (vacío = todos):", key="input_busqueda_tab3")
            conn = get_connection()
            if busqueda:
                df = pd.read_sql("""
                    SELECT p.id, p.cedula, p.nombre, p.apellidos, p.telefono, p.email, p.whatsapp, p.es_menor, p.sexo, p.usa_lentes, p.fecha_nacimiento, p.empresa,
                           e.nombre as estado, m.nombre as municipio
                    FROM pacientes p LEFT JOIN estados e ON p.estado_id = e.id LEFT JOIN municipios m ON p.municipio_id = m.id
                    WHERE p.cedula ILIKE %s OR p.nombre ILIKE %s OR p.apellidos ILIKE %s OR p.telefono ILIKE %s
                    ORDER BY p.apellidos, p.nombre
                """, conn, params=(f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%', f'%{busqueda}%'))
            else:
                df = pd.read_sql("""
                    SELECT p.id, p.cedula, p.nombre, p.apellidos, p.telefono, p.email, p.whatsapp, p.es_menor, p.sexo, p.usa_lentes, p.fecha_nacimiento, p.empresa,
                           e.nombre as estado, m.nombre as municipio
                    FROM pacientes p LEFT JOIN estados e ON p.estado_id = e.id LEFT JOIN municipios m ON p.municipio_id = m.id
                    ORDER BY p.apellidos, p.nombre
                """, conn)
            conn.close()
            if not df.empty:
                if busqueda: st.success(f"✅ Se encontraron **{len(df)}** paciente(s)")
                else: st.info(f"📋 Mostrando todos los pacientes ({len(df)})")
                df_display = df.copy()
                df_display['sexo'] = df_display['sexo'].map({'F': '♀️ F', 'M': '♂️ M'}).fillna('')
                df_display['usa_lentes'] = df_display['usa_lentes'].map({True: ' Sí', False: '❌ No', None: ''})
                df_display['edad'] = df_display['fecha_nacimiento'].apply(lambda x: f"{calcular_edad(x)} años" if pd.notna(x) else '')
                evento = st.dataframe(df_display[['cedula', 'nombre', 'apellidos', 'sexo', 'edad', 'empresa', 'usa_lentes', 'telefono', 'estado', 'municipio']],
                                      use_container_width=True, height=400, on_select="rerun", selection_mode="single-row", key="tabla_pacientes_click")
                if evento.selection.rows:
                    paciente_id = int(df.iloc[evento.selection.rows[0]]['id'])
                    st.success(f"✅ Seleccionado: **{df.iloc[evento.selection.rows[0]]['apellidos']} {df.iloc[evento.selection.rows[0]]['nombre']}**")
                    col_ver, col_edit = st.columns(2)
                    with col_ver:
                        if st.button("👁️ Ver Datos Completos", use_container_width=True, key=f"btn_ver_fila_{paciente_id}"):
                            st.session_state.ver_paciente_id = paciente_id; st.session_state.page = "ver_paciente"; st.rerun()
                    with col_edit:
                        if st.button("✏️ Editar Paciente", use_container_width=True, key=f"btn_edit_fila_{paciente_id}", type="primary"):
                            st.session_state.editar_paciente_id = paciente_id; st.session_state.page = "editar_paciente"; st.rerun()
            else: st.warning("📭 No hay pacientes registrados")

    # ═══════════════════════════════════════════════════════
    # VER PACIENTE
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "ver_paciente":
        if 'ver_paciente_id' in st.session_state:
            paciente_id = st.session_state.ver_paciente_id
            conn = get_connection(); cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id, p.nombre, p.apellidos, p.cedula, p.fecha_nacimiento, p.telefono, p.email, p.direccion, p.whatsapp, p.notas,
                       p.es_menor, p.parentesco, e.nombre, m.nombre, c.nombre, r.nombre || ' ' || r.apellidos, p.sexo, p.usa_lentes, p.empresa
                FROM pacientes p LEFT JOIN estados e ON p.estado_id = e.id LEFT JOIN municipios m ON p.municipio_id = m.id
                LEFT JOIN ciudades c ON p.ciudad_id = c.id LEFT JOIN pacientes r ON p.representante_id = r.id
                WHERE p.id = %s
            """, (paciente_id,))
            paciente = cursor.fetchone(); cursor.close(); conn.close()
            if paciente:
                st.title("️ Datos del Paciente")
                if st.button("⬅️ Volver", key="btn_volver_buscar"):
                    del st.session_state.ver_paciente_id; st.session_state.page = "pacientes"; st.rerun()
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Nombre:** {paciente[1]} {paciente[2]}")
                    st.markdown(f"**Cédula:** {paciente[3] or 'No registrada'}")
                    edad = calcular_edad(paciente[4])
                    st.markdown(f"**Fecha Nac.:** {paciente[4].strftime('%d/%m/%Y') if paciente[4] else 'No registrada'}")
                    if edad is not None: st.markdown(f"**Edad:** {edad} años")
                    st.markdown(f"**Sexo:** {'Femenino' if paciente[16] == 'F' else 'Masculino' if paciente[16] == 'M' else 'No especificado'}")
                    st.markdown(f"**Usa lentes:** {'Sí 👓' if paciente[17] else 'No ❌' if paciente[17] == False else 'No especificado'}")
                with col2:
                    st.markdown(f"**Teléfono:** {paciente[5] or 'No registrado'}")
                    st.markdown(f"**WhatsApp:** {paciente[8] or 'No registrado'}")
                    st.markdown(f"**Email:** {paciente[6] or 'No registrado'}")
                    st.markdown(f"**Empresa:** {paciente[18] or 'No registrada'}")
                st.subheader("📍 Dirección")
                dir_comp = [x for x in [paciente[7], paciente[12], paciente[13], paciente[14]] if x]
                st.markdown(", ".join(dir_comp) if dir_comp else "No registrada")
                if paciente[9]:
                    st.subheader(" Notas"); st.markdown(paciente[9])
                st.markdown("---")
                if st.button("✏️ Editar este Paciente", use_container_width=True, key="btn_edit_ver", type="primary"):
                    st.session_state.editar_paciente_id = paciente_id; st.session_state.page = "editar_paciente"; st.rerun()
            else:
                st.error("Paciente no encontrado"); st.session_state.page = "pacientes"; st.rerun()
        else:
            st.error("No hay paciente seleccionado"); st.session_state.page = "pacientes"; st.rerun()

    # ══════════════════════════════════════════════════════
    # EDITAR PACIENTE
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "editar_paciente":
        if 'editar_paciente_id' in st.session_state:
            paciente_id = st.session_state.editar_paciente_id
            conn = get_connection(); cursor = conn.cursor()
            cursor.execute("""
                SELECT id, nombre, apellidos, cedula, fecha_nacimiento, telefono, email, direccion, whatsapp, notas,
                       es_menor, representante_id, parentesco, estado_id, municipio_id, ciudad_id, sexo, usa_lentes, empresa
                FROM pacientes WHERE id = %s
            """, (paciente_id,))
            paciente = cursor.fetchone(); cursor.close(); conn.close()
            if paciente:
                st.title("✏️ Editar Paciente")
                st.info(f"Editando: **{paciente[1]} {paciente[2]}** (ID: {paciente_id})")
                if st.button("⬅️ Volver a Búsqueda", key="btn_volver_busqueda_edit"):
                    del st.session_state.editar_paciente_id; st.session_state.page = "pacientes"; st.rerun()
                with st.form(f"editar_paciente_{paciente_id}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nombre = st.text_input("Nombre(s) *", value=paciente[1], key=f"edit_nom_{paciente_id}")
                        cedula = st.text_input("Cédula", value=paciente[3] or "", key=f"edit_ced_{paciente_id}")
                        telefono = st.text_input("Teléfono", value=paciente[5] or "", key=f"edit_tel_{paciente_id}")
                        email = st.text_input("Email", value=paciente[6] or "", key=f"edit_email_{paciente_id}")
                        empresa = st.text_input(" Empresa", value=paciente[18] or "", key=f"edit_empresa_{paciente_id}")
                    with col2:
                        apellidos = st.text_input("Apellidos *", value=paciente[2], key=f"edit_ape_{paciente_id}")
                        fecha_nac = st.date_input(
                            "Fecha de Nacimiento (DD/MM/AAAA)",
                            value=paciente[4],
                            min_value=date(1900, 1, 1),
                            max_value=date.today(),
                            format="DD/MM/YYYY",
                            key=f"edit_fn_{paciente_id}"
                        )
                        whatsapp = st.text_input("WhatsApp", value=paciente[8] or "", key=f"edit_wa_{paciente_id}")
                    if fecha_nac: st.info(f"🎂 Edad actual: **{calcular_edad(fecha_nac)} años**")
                    col1, col2 = st.columns(2)
                    with col1:
                        sexo_act = "Femenino" if paciente[16] == "F" else "Masculino" if paciente[16] == "M" else "Seleccionar..."
                        sexo = st.selectbox("Sexo", ["Seleccionar...", "Femenino", "Masculino"], index=["Seleccionar...", "Femenino", "Masculino"].index(sexo_act), key=f"edit_sexo_{paciente_id}")
                    with col2:
                        ul_act = "Sí" if paciente[17] == True else "No" if paciente[17] == False else "Seleccionar..."
                        usa_lentes = st.selectbox("¿Usa lentes?", ["Seleccionar...", "Sí", "No"], index=["Seleccionar...", "Sí", "No"].index(ul_act), key=f"edit_lentes_{paciente_id}")
                    conn = get_connection()
                    estados_df = pd.read_sql("SELECT id, nombre FROM estados ORDER BY nombre", conn); conn.close()
                    estado_act = ""
                    if paciente[13]:
                        m = estados_df[estados_df['id'] == paciente[13]]
                        estado_act = m['nombre'].values[0] if not m.empty else ""
                    estado_opc = ["Seleccionar..."] + estados_df['nombre'].tolist()
                    estado_sel = st.selectbox("🇪 Estado", estado_opc, index=estado_opc.index(estado_act) if estado_act in estado_opc else 0, key=f"edit_est_{paciente_id}")
                    municipio_sel = "Seleccionar..."; ciudad_sel = "Seleccionar..."
                    municipios_df = pd.DataFrame(); ciudades_df = pd.DataFrame()
                    if estado_sel != "Seleccionar...":
                        eid = int(estados_df[estados_df['nombre'] == estado_sel]['id'].values[0])
                        conn = get_connection()
                        municipios_df = pd.read_sql("SELECT id, nombre FROM municipios WHERE estado_id = %s ORDER BY nombre", conn, params=(eid,)); conn.close()
                        if not municipios_df.empty:
                            mun_act = ""
                            if paciente[14]:
                                m = municipios_df[municipios_df['id'] == paciente[14]]
                                mun_act = m['nombre'].values[0] if not m.empty else ""
                            mun_opc = ["Seleccionar..."] + municipios_df['nombre'].tolist()
                            municipio_sel = st.selectbox("🏘️ Municipio", mun_opc, index=mun_opc.index(mun_act) if mun_act in mun_opc else 0, key=f"edit_mun_{paciente_id}")
                            if municipio_sel != "Seleccionar...":
                                mid = int(municipios_df[municipios_df['nombre'] == municipio_sel]['id'].values[0])
                                conn = get_connection()
                                ciudades_df = pd.read_sql("SELECT id, nombre FROM ciudades WHERE municipio_id = %s ORDER BY nombre", conn, params=(mid,)); conn.close()
                                if not ciudades_df.empty:
                                    ciu_act = ""
                                    if paciente[15]:
                                        m = ciudades_df[ciudades_df['id'] == paciente[15]]
                                        ciu_act = m['nombre'].values[0] if not m.empty else ""
                                    ciu_opc = ["Seleccionar..."] + ciudades_df['nombre'].tolist()
                                    ciudad_sel = st.selectbox("️ Ciudad/Parroquia", ciu_opc, index=ciu_opc.index(ciu_act) if ciu_act in ciu_opc else 0, key=f"edit_ciu_{paciente_id}")
                    direccion = st.text_area("📍 Dirección", value=paciente[7] or "", key=f"edit_dir_{paciente_id}")
                    notas = st.text_area("📝 Notas", value=paciente[9] or "", key=f"edit_notas_{paciente_id}")
                    col_b1, col_b2 = st.columns(2)
                    with col_b1: submitted = st.form_submit_button("💾 Guardar Cambios", use_container_width=True, type="primary")
                    with col_b2: cancelar = st.form_submit_button("❌ Cancelar", use_container_width=True)
                    if submitted:
                        if nombre and apellidos:
                            try:
                                estado_id = municipio_id = ciudad_id = None
                                if estado_sel != "Seleccionar...":
                                    estado_id = int(estados_df[estados_df['nombre'] == estado_sel]['id'].values[0])
                                    if municipio_sel != "Seleccionar..." and not municipios_df.empty:
                                        municipio_id = int(municipios_df[municipios_df['nombre'] == municipio_sel]['id'].values[0])
                                        if ciudad_sel != "Seleccionar..." and not ciudades_df.empty:
                                            ciudad_id = int(ciudades_df[ciudades_df['nombre'] == ciudad_sel]['id'].values[0])
                                sexo_db = "F" if sexo == "Femenino" else "M" if sexo == "Masculino" else None
                                ul_db = True if usa_lentes == "Sí" else False if usa_lentes == "No" else None
                                conn = get_connection(); cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE pacientes SET nombre=%s, apellidos=%s, cedula=%s, fecha_nacimiento=%s, telefono=%s, email=%s,
                                    direccion=%s, whatsapp=%s, notas=%s, estado_id=%s, municipio_id=%s, ciudad_id=%s, sexo=%s, usa_lentes=%s, empresa=%s
                                    WHERE id=%s
                                """, (nombre, apellidos, cedula if cedula else None, fecha_nac, telefono, email, direccion, whatsapp, notas,
                                      estado_id, municipio_id, ciudad_id, sexo_db, ul_db, empresa if empresa else None, paciente_id))
                                conn.commit(); cursor.close(); conn.close()
                                st.success(f"✅ Paciente **{nombre} {apellidos}** actualizado"); st.balloons()
                                del st.session_state.editar_paciente_id; st.session_state.page = "pacientes"; st.rerun()
                            except Exception as e:
                                st.error(f" Ya existe otro paciente con la cédula **{cedula}**" if 'uq_pacientes_cedula' in str(e) else f"❌ Error: {e}")
                        else: st.error("️ Nombre y Apellidos obligatorios")
                    if cancelar:
                        del st.session_state.editar_paciente_id; st.session_state.page = "pacientes"; st.rerun()
            else:
                st.error("Paciente no encontrado"); st.session_state.page = "pacientes"; st.rerun()
        else:
            st.error("No hay paciente seleccionado"); st.session_state.page = "pacientes"; st.rerun()

    # ═══════════════════════════════════════════════════════
    #  EXÁMENES VISUALES + HISTORIAL
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "examenes":
        st.title("🔬 Exámenes Visuales")
        conn = get_connection()
        pac_df = pd.read_sql("SELECT id, nombre, apellidos, cedula FROM pacientes ORDER BY apellidos", conn); conn.close()
        if pac_df.empty:
            st.warning("️ Debes registrar un paciente primero."); st.stop()
        tab_main, tab_hist = st.tabs(["📝 Nuevo Examen", "📋 Historial Clínico"])
        with tab_main:
            pac_opts = {f"{r['apellidos']} {r['nombre']} ({r['cedula'] or 'Sin Cédula'})": int(r['id']) for _, r in pac_df.iterrows()}
            paciente_id = pac_opts[st.selectbox("👤 Paciente para Nuevo Examen:", list(pac_opts.keys()), key="sel_pac_examen")]
            st.markdown("---")
            t1, t2, t3, t4, t5, t6 = st.tabs(["1️⃣ Antecedentes", "2️ Historial", "3️ Preguntas", "4️⃣ Pruebas", "5️ Refracción", "6️⃣ Diagnóstico"])
            with t1:
                st.subheader("1.1 Antecedentes Médicos")
                c1, c2, c3, c4 = st.columns(4)
                diabetes = c1.checkbox("Diabetes", key="ex_diabetes"); hipertension = c2.checkbox("Hipertensión", key="ex_hipertension")
                embarazo = c3.checkbox("Embarazo", key="ex_embarazo"); ant_otros = c4.text_input("Otro", key="ex_ant_otros")
                st.subheader("1.2 Síntomas Visuales")
                c1, c2, c3, c4, c5 = st.columns(5)
                lagrimeo = c1.checkbox("Lagrimeo", key="ex_lagrimeo"); v_borrosa = c2.checkbox("Visión Borrosa", key="ex_v_borrosa")
                ardor = c3.checkbox("Ardor/Irritación", key="ex_ardor"); comezon = c4.checkbox("Comezón", key="ex_comezon"); legana = c5.checkbox("Legaña", key="ex_legana")
                c1, c2, c3, c4, c5 = st.columns(5)
                infeccion = c1.checkbox("Infección", key="ex_infeccion"); dolor_c = c2.checkbox("Dolor Cabeza", key="ex_dolor_c")
                destellos = c3.checkbox("Destellos Luz", key="ex_destellos"); resequedad = c4.checkbox("Resequedad", key="ex_resequedad"); sint_otros = c5.text_input("Otro", key="ex_sint_otros")
                notas_sint = st.text_area("Notas de Síntomas", key="ex_notas_sint")
            with t2:
                st.subheader("2. Graduación Anterior")
                c1, c2, c3 = st.columns(3)
                od_esf_a = c1.number_input("ESF OD", key="ex_od_esf_a", step=0.25); od_cil_a = c2.number_input("CIL OD", key="ex_od_cil_a", step=0.25); od_eje_a = c3.number_input("EJE OD", key="ex_od_eje_a", step=1)
                oi_esf_a = c1.number_input("ESF OI", key="ex_oi_esf_a", step=0.25); oi_cil_a = c2.number_input("CIL OI", key="ex_oi_cil_a", step=0.25); oi_eje_a = c3.number_input("EJE OI", key="ex_oi_eje_a", step=1)
                c1, c2 = st.columns(2)
                add_a = c1.number_input("ADD", key="ex_add_a", step=0.25); di_a = c2.number_input("DI", key="ex_di_a", step=0.5)
                st.subheader("Armazón Anterior")
                c1, c2, c3 = st.columns(3)
                arm_tipo = c1.text_input("Tipo", key="ex_arm_tipo"); arm_antig = c2.text_input("Antigüedad", key="ex_arm_antig"); arm_uso = c3.text_input("Uso", key="ex_arm_uso")
                mat_trat = st.text_input("Material y tratamientos", key="ex_mat_trat")
                comp_vis = st.text_area("Comportamiento Visual Anterior", key="ex_comp_vis")
            with t3:
                st.subheader("3. Preguntas de Poder")
                c1, c2, c3, c4 = st.columns(4)
                corr_lej = c1.checkbox("Lejana", key="ex_corr_lej"); corr_int = c2.checkbox("Intermedia", key="ex_corr_int")
                corr_cer = c3.checkbox("Cercana", key="ex_corr_cer"); corr_otr = c4.text_input("Otras", key="ex_corr_otr")
                c1, c2, c3, c4, c5 = st.columns(5)
                nec_corr = c1.checkbox("Corrección", key="ex_nec_corr"); nec_prot = c2.checkbox("Protección", key="ex_nec_prot")
                nec_opt = c3.checkbox("Optimización", key="ex_nec_opt"); nec_ning = c4.checkbox("Ninguna", key="ex_nec_ning"); nec_otr = c5.text_input("Otras", key="ex_nec_otr")
                c1, c2, c3, c4, c5 = st.columns(5)
                atr_est = c1.checkbox("Estética", key="ex_atr_est"); atr_des = c2.checkbox("Desempeño", key="ex_atr_des")
                atr_prot = c3.checkbox("Protección", key="ex_atr_prot"); atr_ning = c4.checkbox("Ninguno", key="ex_atr_ning"); atr_otr = c5.text_input("Otros", key="ex_atr_otr")
                act_aire = st.text_input("4. Actividades al aire libre", key="ex_act_aire")
                prot_sol = st.text_input("5. Protección del sol", key="ex_prot_sol")
                c1, c2 = st.columns(2)
                mol_sol = c1.checkbox("6. Molestias del sol", key="ex_mol_sol"); prot_azul = c2.checkbox("7. Protege de luz azul", key="ex_prot_azul")
                mol_ref = st.checkbox("8. Molestias por reflejo", key="ex_mol_ref")
                imp_trans = st.selectbox("9. Importancia transparencia", ["Seleccionar...", "Poco", "Mucho", "Nada"], key="ex_imp_trans")
                est_lent = st.text_input("10. Estilo de lentes", key="ex_est_lent")
                col_vest = st.text_input("11. Colores vestuario", key="ex_col_vest")
                c1, c2 = st.columns(2)
                lc_sin = c1.checkbox("12. Ver sin lentes a veces", key="ex_lc_sin"); lc_cuando1 = c2.text_input("¿Cuándo?", key="ex_lc_cuando1")
                c1, c2 = st.columns(2)
                lc_est = c1.checkbox("13. ¿Usar lentes estorba?", key="ex_lc_est"); lc_cuando2 = c2.text_input("¿Cuándo?", key="ex_lc_cuando2")
                lc_emerg = st.text_input("14. Lentes de emergencia", key="ex_lc_emerg")
            with t4:
                st.subheader("4.1 Agudeza Visual")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**Lejos CC**")
                    av_l_cc_od = st.text_input("OD", key="ex_av_l_cc_od"); av_l_cc_oi = st.text_input("OI", key="ex_av_l_cc_oi"); av_l_cc_ao = st.text_input("AO", key="ex_av_l_cc_ao")
                    st.markdown("**Lejos SC**")
                    av_l_sc_od = st.text_input("OD", key="ex_av_l_sc_od"); av_l_sc_oi = st.text_input("OI", key="ex_av_l_sc_oi"); av_l_sc_ao = st.text_input("AO", key="ex_av_l_sc_ao")
                with c2:
                    st.markdown("**Cerca CC**")
                    av_c_cc_od = st.text_input("OD", key="ex_av_c_cc_od"); av_c_cc_oi = st.text_input("OI", key="ex_av_c_cc_oi"); av_c_cc_ao = st.text_input("AO", key="ex_av_c_cc_ao")
                    st.markdown("**Cerca SC**")
                    av_c_sc_od = st.text_input("OD", key="ex_av_c_sc_od"); av_c_sc_oi = st.text_input("OI", key="ex_av_c_sc_oi"); av_c_sc_ao = st.text_input("AO", key="ex_av_c_sc_ao")
                with c3:
                    st.markdown("**Estenopeico**")
                    av_est_od = st.text_input("OD", key="ex_av_est_od"); av_est_os = st.text_input("OS", key="ex_av_est_os")
                c1, c2, c3 = st.columns(3)
                amp_od = c1.number_input("Amp. Acomod OD", key="ex_amp_od", step=0.5); amp_oi = c2.number_input("Amp. Acomod OI", key="ex_amp_oi", step=0.5); amp_ao = c3.number_input("Amp. Acomod AO", key="ex_amp_ao", step=0.5)
                c1, c2 = st.columns(2)
                ct_lej_od = c1.text_input("Cover Lejos OD", key="ex_ct_lej_od"); ct_lej_oi = c1.text_input("Cover Lejos OI", key="ex_ct_lej_oi")
                ct_cer_od = c2.text_input("Cover Cerca OD", key="ex_ct_cer_od"); ct_cer_oi = c2.text_input("Cover Cerca OI", key="ex_ct_cer_oi")
                c1, c2 = st.columns(2)
                vc_od = c1.text_input("Visión Colores OD", key="ex_vc_od"); vc_oi = c2.text_input("Visión Colores OI", key="ex_vc_oi")
                c1, c2, c3, c4, c5 = st.columns(5)
                exp_par = c1.text_input("Párpados", key="ex_exp_par"); exp_pes = c2.text_input("Pestañas", key="ex_exp_pes"); exp_con = c3.text_input("Conjuntiva", key="ex_exp_con")
                exp_esc = c4.text_input("Esclera", key="ex_exp_esc"); exp_cor = c5.text_input("Córnea", key="ex_exp_cor")
                c1, c2, c3, c4 = st.columns(4)
                ppc = c1.text_input("P.P.C.", key="ex_ppc"); mot = c2.text_input("Motilidad", key="ex_mot"); pup = c3.text_input("Pupilas", key="ex_pup"); camp = c4.text_input("Campos Vis.", key="ex_camp")
                c1, c2 = st.columns(2)
                oft_od = c1.text_input("Oftalmoscopía OD", key="ex_oft_od"); oft_oi = c2.text_input("Oftalmoscopía OI", key="ex_oft_oi")
                quer_od = c1.text_input("Queratometría OD", key="ex_quer_od"); quer_oi = c2.text_input("Queratometría OI", key="ex_quer_oi")
            with t5:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("5.1 Autorrefractómetro")
                    ar_od_esf = st.number_input("ESF OD", key="ex_ar_od_esf", step=0.25); ar_od_cil = st.number_input("CIL OD", key="ex_ar_od_cil", step=0.25); ar_od_eje = st.number_input("EJE OD", key="ex_ar_od_eje", step=1)
                    ar_oi_esf = st.number_input("ESF OI", key="ex_ar_oi_esf", step=0.25); ar_oi_cil = st.number_input("CIL OI", key="ex_ar_oi_cil", step=0.25); ar_oi_eje = st.number_input("EJE OI", key="ex_ar_oi_eje", step=1)
                    ar_di = st.number_input("DI", key="ex_ar_di", step=0.5)
                    st.subheader("5.3 Lente de Contacto")
                    lc_od_esf_r = st.number_input("ESF OD LC", key="ex_lc_od_esf_r", step=0.25); lc_od_cil_r = st.number_input("CIL OD LC", key="ex_lc_od_cil_r", step=0.25); lc_od_eje_r = st.number_input("EJE OD LC", key="ex_lc_od_eje_r", step=1)
                    lc_oi_esf_r = st.number_input("ESF OI LC", key="ex_lc_oi_esf_r", step=0.25); lc_oi_cil_r = st.number_input("CIL OI LC", key="ex_lc_oi_cil_r", step=0.25); lc_oi_eje_r = st.number_input("EJE OI LC", key="ex_lc_oi_eje_r", step=1)
                    lc_add_r = st.number_input("ADD LC", key="ex_lc_add_r", step=0.25)
                    notas_lc = st.text_area("Notas LC", key="ex_notas_lc")
                with c2:
                    st.subheader("5.2 Graduación Nueva")
                    n_od_esf = st.number_input("ESF OD", key="ex_n_od_esf", step=0.25); n_od_cil = st.number_input("CIL OD", key="ex_n_od_cil", step=0.25); n_od_eje = st.number_input("EJE OD", key="ex_n_od_eje", step=1)
                    n_oi_esf = st.number_input("ESF OI", key="ex_n_oi_esf", step=0.25); n_oi_cil = st.number_input("CIL OI", key="ex_n_oi_cil", step=0.25); n_oi_eje = st.number_input("EJE OI", key="ex_n_oi_eje", step=1)
                    n_add = st.number_input("ADD", key="ex_n_add", step=0.25); n_di = st.number_input("DI", key="ex_n_di", step=0.5)
                    st.subheader("5.4 Agudeza Nueva")
                    ag_n_l_od = st.text_input("Lejos OD", key="ex_ag_n_l_od"); ag_n_l_oi = st.text_input("Lejos OI", key="ex_ag_n_l_oi"); ag_n_l_ao = st.text_input("Lejos AO", key="ex_ag_n_l_ao")
                    ag_n_c_od = st.text_input("Cerca OD", key="ex_ag_n_c_od"); ag_n_c_oi = st.text_input("Cerca OI", key="ex_ag_n_c_oi"); ag_n_c_ao = st.text_input("Cerca AO", key="ex_ag_n_c_ao")
                notas_gen = st.text_area("Notas Generales", key="ex_notas_gen")
            with t6:
                st.subheader("6. Diagnóstico")
                c1, c2, c3, c4, c5 = st.columns(5)
                diag_mio = c1.checkbox("Miopía", key="ex_diag_mio"); diag_hip = c2.checkbox("Hipermetropía", key="ex_diag_hip")
                diag_ast = c3.checkbox("Astigmatismo", key="ex_diag_ast"); diag_pre = c4.checkbox("Presbicia", key="ex_diag_pre"); diag_otr = c5.text_input("Otro", key="ex_diag_otr")
                accedio_lc = st.checkbox("¿Accedió a prueba de LC?", key="ex_accedio_lc")
                c1, c2, c3 = st.columns(3)
                with c1:
                    pio_od = st.number_input("Presión OD", key="ex_pio_od", step=0.1); prox_cita = st.date_input("Próxima Cita", key="ex_prox_cita")
                with c2:
                    pio_oi = st.number_input("Presión OI", key="ex_pio_oi", step=0.1); tratamiento = st.text_input("Tratamiento", key="ex_tratamiento")
                with c3:
                    fecha_examen = st.date_input("Fecha Examen", value=date.today(), key="ex_fecha")
                    hora_examen = st.time_input("Hora Examen", value=datetime.now().time(), key="ex_hora")
                if st.button("💾 GUARDAR EXAMEN COMPLETO", type="primary", use_container_width=True):
                    try:
                        datos = {
                            'paciente_id': paciente_id, 'doctor_id': None, 'fecha_examen': fecha_examen, 'hora_examen': hora_examen,
                            'diabetes': diabetes, 'hipertension': hipertension, 'embarazo': embarazo, 'antecedentes_otros': ant_otros,
                            'lagrimeo': lagrimeo, 'vision_borrosa': v_borrosa, 'ardor_irritacion': ardor, 'comezon': comezon, 'legana': legana,
                            'infeccion': infeccion, 'dolor_cabeza': dolor_c, 'destellos_luz': destellos, 'resequedad_ocular': resequedad, 'sintomas_otros': sint_otros, 'notas_sintomas': notas_sint,
                            'grad_ant_od_esf': od_esf_a, 'grad_ant_od_cil': od_cil_a, 'grad_ant_od_eje': od_eje_a,
                            'grad_ant_oi_esf': oi_esf_a, 'grad_ant_oi_cil': oi_cil_a, 'grad_ant_oi_eje': oi_eje_a, 'grad_ant_add': add_a, 'grad_ant_di': di_a,
                            'armazon_anterior_tipo': arm_tipo, 'armazon_anterior_antiguedad': arm_antig, 'armazon_anterior_uso': arm_uso,
                            'tipo_material_tratamientos': mat_trat, 'comportamiento_visual_anterior': comp_vis,
                            'corr_lejana': corr_lej, 'corr_intermedia': corr_int, 'corr_cercana': corr_cer, 'corr_otras': corr_otr,
                            'necesidad_correccion': nec_corr, 'necesidad_proteccion': nec_prot, 'necesidad_optimizacion': nec_opt, 'necesidad_ninguna': nec_ning, 'necesidad_otras': nec_otr,
                            'atributo_estetica': atr_est, 'atributo_desempeno': atr_des, 'atributo_proteccion': atr_prot, 'atributo_ninguno': atr_ning, 'atributo_otros': atr_otr,
                            'actividades_aire_libre': act_aire, 'proteccion_sol': prot_sol, 'molestias_sol': mol_sol, 'proteccion_luz_azul': prot_azul,
                            'molestias_reflejo': mol_ref, 'importancia_transparencia': imp_trans if imp_trans != "Seleccionar..." else None,
                            'estilo_lentes': est_lent, 'colores_vestuario': col_vest,
                            'lentes_contacto_sin_lentes': lc_sin, 'lentes_contacto_cuando': lc_cuando1, 'lentes_contacto_estorba': lc_est,
                            'lentes_contacto_estorba_cuando': lc_cuando2, 'lentes_emergencia': lc_emerg,
                            'av_lejos_cc_od': av_l_cc_od, 'av_lejos_cc_oi': av_l_cc_oi, 'av_lejos_cc_ao': av_l_cc_ao,
                            'av_lejos_sc_od': av_l_sc_od, 'av_lejos_sc_oi': av_l_sc_oi, 'av_lejos_sc_ao': av_l_sc_ao,
                            'av_cerca_cc_od': av_c_cc_od, 'av_cerca_cc_oi': av_c_cc_oi, 'av_cerca_cc_ao': av_c_cc_ao,
                            'av_cerca_sc_od': av_c_sc_od, 'av_cerca_sc_oi': av_c_sc_oi, 'av_cerca_sc_ao': av_c_sc_ao,
                            'av_estenopeico_od': av_est_od, 'av_estenopeico_os': av_est_os,
                            'amp_acomodacion_od': amp_od, 'amp_acomodacion_oi': amp_oi, 'amp_acomodacion_ao': amp_ao,
                            'cover_test_lejos_od': ct_lej_od, 'cover_test_lejos_oi': ct_lej_oi, 'cover_test_cerca_od': ct_cer_od, 'cover_test_cerca_oi': ct_cer_oi,
                            'vision_colores_od': vc_od, 'vision_colores_oi': vc_oi,
                            'exploracion_parparados': exp_par, 'exploracion_pestanas': exp_pes, 'exploracion_conjuntiva': exp_con, 'exploracion_esclera': exp_esc, 'exploracion_cornea': exp_cor,
                            'ppc': ppc, 'motilidad': mot, 'pupilas': pup, 'campos_visuales': camp,
                            'oftalmoscopia_od': oft_od, 'oftalmoscopia_oi': oft_oi, 'queratometria_od': quer_od, 'queratometria_oi': quer_oi,
                            'auto_od_esf': ar_od_esf, 'auto_od_cil': ar_od_cil, 'auto_od_eje': ar_od_eje,
                            'auto_oi_esf': ar_oi_esf, 'auto_oi_cil': ar_oi_cil, 'auto_oi_eje': ar_oi_eje, 'auto_di': ar_di,
                            'nueva_od_esf': n_od_esf, 'nueva_od_cil': n_od_cil, 'nueva_od_eje': n_od_eje,
                            'nueva_oi_esf': n_oi_esf, 'nueva_oi_cil': n_oi_cil, 'nueva_oi_eje': n_oi_eje, 'nueva_add': n_add, 'nueva_di': n_di,
                            'lc_od_esf': lc_od_esf_r, 'lc_od_cil': lc_od_cil_r, 'lc_od_eje': lc_od_eje_r,
                            'lc_oi_esf': lc_oi_esf_r, 'lc_oi_cil': lc_oi_cil_r, 'lc_oi_eje': lc_oi_eje_r, 'lc_add': lc_add_r, 'notas_lc': notas_lc,
                            'agudeza_nueva_lejos_od': ag_n_l_od, 'agudeza_nueva_lejos_oi': ag_n_l_oi, 'agudeza_nueva_lejos_ao': ag_n_l_ao,
                            'agudeza_nueva_cerca_od': ag_n_c_od, 'agudeza_nueva_cerca_oi': ag_n_c_oi, 'agudeza_nueva_cerca_ao': ag_n_c_ao,
                            'notas_generales': notas_gen,
                            'diagnostico_miopia': diag_mio, 'diagnostico_hipermetropia': diag_hip, 'diagnostico_astigmatismo': diag_ast, 'diagnostico_presbicia': diag_pre, 'diagnostico_otro': diag_otr,
                            'accedio_prueba_lc': accedio_lc, 'presion_od': pio_od, 'presion_oi': pio_oi, 'tratamiento': tratamiento, 'proxima_cita': prox_cita, 'estado': 'Completado'
                        }
                        conn = get_connection(); cur = conn.cursor()
                        cols = ', '.join(datos.keys()); vals = ', '.join(['%s'] * len(datos))
                        cur.execute(f"INSERT INTO examenes ({cols}) VALUES ({vals}) RETURNING id", list(datos.values()))
                        examen_id = cur.fetchone()[0]; conn.commit(); cur.close(); conn.close()
                        st.success(f"✅ Examen guardado (ID: {examen_id})"); st.balloons()
                    except Exception as e:
                        st.error(f"❌ Error al guardar: {e}")
        with tab_hist:
            st.subheader("📋 Historial Clínico")
            pac_opts_hist = {f"{r['apellidos']} {r['nombre']} ({r['cedula'] or 'Sin Cédula'})": int(r['id']) for _, r in pac_df.iterrows()}
            paciente_id_hist = pac_opts_hist[st.selectbox(" Paciente:", list(pac_opts_hist.keys()), key="sel_pac_hist")]
            conn = get_connection()
            hist_df = pd.read_sql("""
                SELECT id, fecha_examen, hora_examen, estado, nueva_od_esf, nueva_od_cil, nueva_od_eje, nueva_oi_esf, nueva_oi_cil, nueva_oi_eje, nueva_add
                FROM examenes WHERE paciente_id = %s ORDER BY fecha_examen DESC, hora_examen DESC
            """, conn, params=(paciente_id_hist,)); conn.close()
            if not hist_df.empty:
                hist_df['fecha_examen'] = pd.to_datetime(hist_df['fecha_examen']).dt.strftime('%d/%m/%Y')
                hist_df['hora_examen'] = hist_df['hora_examen'].astype(str).str[:5]
                st.dataframe(hist_df, use_container_width=True, height=300)
                examen_sel = st.selectbox("Ver detalle:", [f"ID: {row['id']} - {row['fecha_examen']} {row['hora_examen']}" for _, row in hist_df.iterrows()], key="sel_examen_det")
                if examen_sel and st.button("👁️ Ver Ficha", use_container_width=True, type="primary", key="btn_ver_ficha"):
                    eid = int(examen_sel.split("ID: ")[1].split(" - ")[0])
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute("SELECT * FROM examenes WHERE id = %s", (eid,))
                    cols = [d[0] for d in cur.description]; ed = dict(zip(cols, cur.fetchone())); cur.close(); conn.close()
                    diag = [x for x, f in [("Miopía", ed.get('diagnostico_miopia')), ("Hipermetropía", ed.get('diagnostico_hipermetropia')),
                            ("Astigmatismo", ed.get('diagnostico_astigmatismo')), ("Presbicia", ed.get('diagnostico_presbicia'))] if f]
                    if ed.get('diagnostico_otro'): diag.append(ed['diagnostico_otro'])
                    st.markdown(f"### 📄 Ficha ID {eid}")
                    st.info("**Diagnóstico:** " + (", ".join(diag) if diag else "Sin diagnóstico"))
                    st.markdown(f"**OD:** Esf {ed.get('nueva_od_esf')}, Cil {ed.get('nueva_od_cil')}, Eje {ed.get('nueva_od_eje')} | **OI:** Esf {ed.get('nueva_oi_esf')}, Cil {ed.get('nueva_oi_cil')}, Eje {ed.get('nueva_oi_eje')} | **ADD:** {ed.get('nueva_add')}")
            else: st.info("📭 Sin exámenes registrados para este paciente.")

    # ═══════════════════════════════════════════════════════
    #  CONSULTAS + LABORATORIO + PDF
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "consultas":
        st.title(" Control de Consultas y Envío a Laboratorio")
        conn = get_connection()
        pac_df = pd.read_sql("SELECT id, cedula, nombre, apellidos, sexo, telefono, fecha_nacimiento FROM pacientes ORDER BY apellidos, nombre", conn); conn.close()
        if pac_df.empty:
            st.warning("️ Debes registrar un paciente primero."); st.stop()
        pac_opts = {f"{r['apellidos']} {r['nombre']} (V-{r['cedula'] or 'S/C'})": int(r['id']) for _, r in pac_df.iterrows()}
        paciente_id = pac_opts[st.selectbox(" Paciente:", list(pac_opts.keys()), key="con_pac_sel")]
        tab_con, tab_pdf = st.tabs(["🩺 Consulta", " Generar PDF"])
        with tab_con:
            c_sum, c_main = st.columns([1, 3])
            with c_sum:
                pr = pac_df[pac_df['id'] == paciente_id].iloc[0]
                st.markdown("#### 📋 Ficha del Paciente")
                st.markdown(f"**Cédula:** {pr['cedula'] or 'S/C'}")
                st.markdown(f"**Nombres:** {pr['nombre']} {pr['apellidos']}")
                st.markdown(f"**Sexo:** {pr['sexo'] or '—'}")
                st.markdown(f"**Edad:** {calcular_edad(pr['fecha_nacimiento']) or '—'} años")
                st.markdown(f"**Teléfono:** {pr['telefono'] or '—'}")
                st.markdown("---")
                conn = get_connection()
                hist = pd.read_sql("SELECT id, fecha_consulta FROM consultas WHERE paciente_id = %s ORDER BY fecha_consulta DESC", conn, params=(paciente_id,)); conn.close()
                st.markdown("**🗓️ Historial:**")
                if not hist.empty:
                    for _, h in hist.iterrows():
                        if st.button(f"{pd.to_datetime(h['fecha_consulta']).strftime('%d/%m/%Y')} (ID {h['id']})", key=f"con_h_{h['id']}", use_container_width=True):
                            st.session_state.consulta_id = int(h['id']); st.rerun()
                else: st.info("Sin consultas previas")
                if st.button("➕ Nueva Consulta", key="con_nueva", type="primary", use_container_width=True):
                    st.session_state.consulta_id = None; st.rerun()
            with c_main:
                c = None
                if st.session_state.consulta_id:
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute("SELECT * FROM consultas WHERE id = %s", (st.session_state.consulta_id,))
                    fila_c = cur.fetchone()
                    if fila_c:
                        c = dict(zip([d[0] for d in cur.description], fila_c))
                    cur.close(); conn.close()
                    if c: st.success(f"✏️ Editando consulta ID {c['id']} del {pd.to_datetime(c['fecha_consulta']).strftime('%d/%m/%Y')}")
                if c is None: st.info("➕ Creando NUEVA consulta")
                def gv(campo, default=""):
                    if c is not None and c.get(campo) is not None: return c.get(campo)
                    return default
                def nv(campo, default=0.0):
                    if c is not None and c.get(campo) is not None: return float(c.get(campo))
                    return default
                t_datos, t_ant, t_grad = st.tabs(["📝 Datos de Consulta", "🩺 Antecedentes y Examen Ocular", "🔬 Graduación y Envío a Lab"])
                with t_datos:
                    fecha_con = st.date_input("Fecha de consulta:", value=gv('fecha_consulta', date.today()) or date.today(), key="con_fecha")
                    motivo = st.text_area("Motivo de Consulta:", value=gv('motivo'), key="con_motivo", height=80)
                    sintomas = st.text_area("Síntomas:", value=gv('sintomas'), key="con_sintomas", height=80)
                    diagnostico = st.text_area("Diagnóstico:", value=gv('diagnostico'), key="con_diag", height=80)
                with t_ant:
                    ca1, ca2 = st.columns(2)
                    with ca1:
                        st.markdown("##### Antecedentes")
                        usa_lentes_rx = st.radio("¿Usa Lentes?", ["SI", "NO"], index=0 if gv('usa_lentes_rx', False) == True else 1, horizontal=True, key="con_usa_lentes")
                        ant_pers = st.text_area("Antecedentes Personales:", value=gv('antecedentes_personales'), key="con_ant_pers", height=70)
                        alergias = st.text_area("Alergias:", value=gv('alergias'), key="con_alergias", height=70)
                        ant_fam = st.text_area("Antecedentes Familiares:", value=gv('antecedentes_familiares'), key="con_ant_fam", height=70)
                        cirugias = st.text_area("Cirugías previas:", value=gv('cirugias_previas'), key="con_cirugias", height=70)
                    with ca2:
                        st.markdown("##### Examen Ocular / Funcional")
                        avl = {}; avc = {}
                        st.markdown("**Agudeza Visual Lejana**")
                        h1 = st.columns(4); h1[0].markdown("**Ojo**"); h1[1].markdown("**SIN RX**"); h1[2].markdown("**RX ANT**"); h1[3].markdown("**PH**")
                        for fila in ['od', 'oi', 'ao']:
                            cx = st.columns(4); cx[0].markdown(f"**{fila.upper()}**")
                            avl[f'sin_{fila}'] = cx[1].text_input("SIN RX", value=gv(f'avl_sin_rx_{fila}'), key=f"con_avl_sin_{fila}", label_visibility="collapsed")
                            avl[f'rx_{fila}'] = cx[2].text_input("RX ANT", value=gv(f'avl_rx_ant_{fila}'), key=f"con_avl_rx_{fila}", label_visibility="collapsed")
                            avl[f'ph_{fila}'] = cx[3].text_input("PH", value=gv(f'avl_ph_{fila}'), key=f"con_avl_ph_{fila}", label_visibility="collapsed")
                        st.markdown("**Agudeza Visual Cercana**")
                        h2 = st.columns(4); h2[0].markdown("**Ojo**"); h2[1].markdown("**SIN RX**"); h2[2].markdown("**RX ANT**"); h2[3].markdown("**PH**")
                        for fila in ['od', 'oi', 'ao']:
                            cx = st.columns(4); cx[0].markdown(f"**{fila.upper()}**")
                            avc[f'sin_{fila}'] = cx[1].text_input("SIN RX", value=gv(f'avc_sin_rx_{fila}'), key=f"con_avc_sin_{fila}", label_visibility="collapsed")
                            avc[f'rx_{fila}'] = cx[2].text_input("RX ANT", value=gv(f'avc_rx_ant_{fila}'), key=f"con_avc_rx_{fila}", label_visibility="collapsed")
                            avc[f'ph_{fila}'] = cx[3].text_input("PH", value=gv(f'avc_ph_{fila}'), key=f"con_avc_ph_{fila}", label_visibility="collapsed")
                        cq = st.columns(2)
                        quer_od = cq[0].text_input("Queratometría OD", value=gv('queratometria_od'), key="con_quer_od")
                        quer_oi = cq[1].text_input("Queratometría OI", value=gv('queratometria_oi'), key="con_quer_oi")
                        st.markdown("**Refracciones**")
                        h3 = st.columns(4); h3[0].markdown("**Ojo**"); h3[1].markdown("**Esfera**"); h3[2].markdown("**Cilindro**"); h3[3].markdown("**Eje**")
                        r1 = st.columns(4); r1[0].markdown("**OD**")
                        refr_od_esf = r1[1].number_input("Esfera", step=0.25, value=nv('refr_od_esf'), key="con_refr_od_esf", label_visibility="collapsed")
                        refr_od_cil = r1[2].number_input("Cilindro", step=0.25, value=nv('refr_od_cil'), key="con_refr_od_cil", label_visibility="collapsed")
                        refr_od_eje = r1[3].number_input("Eje", step=1.0, value=nv('refr_od_eje'), key="con_refr_od_eje", label_visibility="collapsed")
                        r2 = st.columns(4); r2[0].markdown("**OI**")
                        refr_oi_esf = r2[1].number_input("Esfera", step=0.25, value=nv('refr_oi_esf'), key="con_refr_oi_esf", label_visibility="collapsed")
                        refr_oi_cil = r2[2].number_input("Cilindro", step=0.25, value=nv('refr_oi_cil'), key="con_refr_oi_cil", label_visibility="collapsed")
                        refr_oi_eje = r2[3].number_input("Eje", step=1.0, value=nv('refr_oi_eje'), key="con_refr_oi_eje", label_visibility="collapsed")
                with t_grad:
                    g = None
                    if c is not None:
                        conn = get_connection()
                        gdf = pd.read_sql("SELECT * FROM graduaciones_lab WHERE consulta_id = %s ORDER BY id DESC LIMIT 1", conn, params=(c['id'],)); conn.close()
                        if not gdf.empty: g = gdf.iloc[0].to_dict()
                    def gv2(campo, default=0.0):
                        if g is not None and g.get(campo) is not None: return float(g.get(campo))
                        return default
                    def tv(campo):
                        if g is not None and g.get(campo) is not None: return str(g.get(campo))
                        return ""
                    if g is not None: st.success(f"📦 Graduación cargada (Pedido ID {int(g['id'])})")
                    else: st.info("🔬 Sin graduación guardada para esta consulta")
                    st.markdown("##### Rx Final")
                    hg = st.columns(9)
                    for i, htxt in enumerate(["Ojo", "Esfera", "Cilindro", "Eje", "Prisma", "AV Lejos", "AV Cerca", "ADD", "Tipo Lente"]): hg[i].markdown(f"**{htxt}**")
                    rx = {}
                    for fila in ['od', 'oi']:
                        cg = st.columns(9); cg[0].markdown(f"**{fila.upper()}**")
                        rx[f'{fila}_esf'] = cg[1].number_input("Esfera", step=0.25, value=gv2(f'rx_{fila}_esf'), key=f"grad_{fila}_esf", label_visibility="collapsed")
                        rx[f'{fila}_cil'] = cg[2].number_input("Cilindro", step=0.25, value=gv2(f'rx_{fila}_cil'), key=f"grad_{fila}_cil", label_visibility="collapsed")
                        rx[f'{fila}_eje'] = cg[3].number_input("Eje", step=1.0, value=gv2(f'rx_{fila}_eje'), key=f"grad_{fila}_eje", label_visibility="collapsed")
                        rx[f'{fila}_prisma'] = cg[4].text_input("Prisma", value=tv(f'rx_{fila}_prisma'), key=f"grad_{fila}_prisma", label_visibility="collapsed")
                        rx[f'{fila}_avl'] = cg[5].text_input("AV Lejos", value=tv(f'rx_{fila}_av_lejos'), key=f"grad_{fila}_avl", label_visibility="collapsed")
                        rx[f'{fila}_avc'] = cg[6].text_input("AV Cerca", value=tv(f'rx_{fila}_av_cerca'), key=f"grad_{fila}_avc", label_visibility="collapsed")
                        rx[f'{fila}_add'] = cg[7].number_input("ADD", step=0.25, value=gv2(f'rx_{fila}_add'), key=f"grad_{fila}_add", label_visibility="collapsed")
                        rx[f'{fila}_tipo'] = cg[8].text_input("Tipo", value=tv(f'rx_{fila}_tipo_lente'), key=f"grad_{fila}_tipo", label_visibility="collapsed")
                    st.markdown("##### Selección de Lente y Materiales")
                    conn = get_connection()
                    tipos_df = pd.read_sql("SELECT id, nombre FROM tipos_lente WHERE activo = TRUE ORDER BY nombre", conn)
                    mat_df = pd.read_sql("SELECT id, nombre FROM materiales_lente WHERE activo = TRUE ORDER BY nombre", conn)
                    trat_df = pd.read_sql("SELECT id, nombre FROM tratamientos WHERE activo = TRUE ORDER BY nombre", conn)
                    lab_df = pd.read_sql("SELECT id, nombre FROM laboratorios WHERE activo = TRUE ORDER BY nombre", conn); conn.close()
                    def idx_cat(df_cat, valor_id):
                        if valor_id is None or df_cat.empty: return 0
                        m = df_cat[df_cat['id'] == int(valor_id)]
                        if m.empty: return 0
                        return df_cat['nombre'].tolist().index(m.iloc[0]['nombre']) + 1
                    gl1, gl2 = st.columns(2)
                    with gl1:
                        tipo_sel = st.selectbox("Tipo de lente", ["Seleccionar..."] + tipos_df['nombre'].tolist(), index=idx_cat(tipos_df, g['tipo_lente_id'] if g else None), key="grad_tipo_lente")
                        mat_sel = st.selectbox("Material del lente", ["Seleccionar..."] + mat_df['nombre'].tolist(), index=idx_cat(mat_df, g['material_id'] if g else None), key="grad_material")
                        trat_sel = st.selectbox("Tratamiento", ["Seleccionar..."] + trat_df['nombre'].tolist(), index=idx_cat(trat_df, g['tratamiento_id'] if g else None), key="grad_tratamiento")
                        detalles = st.text_input("Detalles Adicionales", value=tv('detalles_adicionales'), key="grad_detalles")
                    with gl2:
                        st.markdown("**Laboratorio - Fecha y hora de Pedido**")
                        fecha_pedido = st.date_input("Fecha de Pedido", value=(g['fecha_pedido'] if g is not None and g['fecha_pedido'] is not None else date.today()), key="grad_fecha_pedido")
                        lab_sel = st.selectbox("Laboratorio", ["Seleccionar..."] + lab_df['nombre'].tolist(), index=idx_cat(lab_df, g['laboratorio_id'] if g else None), key="grad_laboratorio")
                        opc_fr = ["URGENTE", "HOY", "MAÑANA", "2-3 DÍAS", "1 SEMANA"]
                        fecha_req = st.selectbox("Fecha requerida:", opc_fr, index=opc_fr.index(tv('fecha_requerida')) if tv('fecha_requerida') in opc_fr else 0, key="grad_fecha_req")
                        opc_hr = ["URGENTE", "MAÑANA", "TARDE", "CUALQUIER HORA"]
                        hora_req = st.selectbox("Hora:", opc_hr, index=opc_hr.index(tv('hora_requerida')) if tv('hora_requerida') in opc_hr else 0, key="grad_hora_req")
                st.markdown("---")
                b1, b2, b3, b4, b5 = st.columns(5)
                with b1: guardar_con = st.button("💾 Guardar Consulta", type="primary", use_container_width=True, key="con_guardar")
                with b2: guardar_grad = st.button(" Guardar Graduación y Lab.", use_container_width=True, key="con_guardar_grad")
                with b3: generar_pdf = st.button("📄 Generar PDF", use_container_width=True, key="con_gen_pdf")
                with b4: envio_pedido = st.button(" Envío a Pedido", use_container_width=True, key="con_envio_ped")
                with b5: eliminar_con = st.button("🗑️ Eliminar Consulta", use_container_width=True, key="con_eliminar")
                if guardar_con:
                    datos_con = {
                        'paciente_id': paciente_id, 'fecha_consulta': fecha_con, 'motivo': motivo, 'sintomas': sintomas, 'diagnostico': diagnostico,
                        'usa_lentes_rx': usa_lentes_rx == "SI", 'antecedentes_personales': ant_pers, 'alergias': alergias,
                        'antecedentes_familiares': ant_fam, 'cirugias_previas': cirugias,
                        'avl_sin_rx_od': avl['sin_od'], 'avl_sin_rx_oi': avl['sin_oi'], 'avl_sin_rx_ao': avl['sin_ao'],
                        'avl_rx_ant_od': avl['rx_od'], 'avl_rx_ant_oi': avl['rx_oi'], 'avl_rx_ant_ao': avl['rx_ao'],
                        'avl_ph_od': avl['ph_od'], 'avl_ph_oi': avl['ph_oi'], 'avl_ph_ao': avl['ph_ao'],
                        'avc_sin_rx_od': avc['sin_od'], 'avc_sin_rx_oi': avc['sin_oi'], 'avc_sin_rx_ao': avc['sin_ao'],
                        'avc_rx_ant_od': avc['rx_od'], 'avc_rx_ant_oi': avc['rx_oi'], 'avc_rx_ant_ao': avc['rx_ao'],
                        'avc_ph_od': avc['ph_od'], 'avc_ph_oi': avc['ph_oi'], 'avc_ph_ao': avc['ph_ao'],
                        'queratometria_od': quer_od, 'queratometria_oi': quer_oi,
                        'refr_od_esf': refr_od_esf, 'refr_od_cil': refr_od_cil, 'refr_od_eje': int(refr_od_eje),
                        'refr_oi_esf': refr_oi_esf, 'refr_oi_cil': refr_oi_cil, 'refr_oi_eje': int(refr_oi_eje),
                    }
                    try:
                        conn = get_connection(); cur = conn.cursor()
                        if c is not None:
                            sets = ', '.join([f"{k}=%s" for k in datos_con.keys() if k != 'paciente_id'])
                            vals = [v for k, v in datos_con.items() if k != 'paciente_id'] + [c['id']]
                            cur.execute(f"UPDATE consultas SET {sets} WHERE id=%s", vals); cid = c['id']
                        else:
                            colsq = ', '.join(datos_con.keys()); valsq = ', '.join(['%s'] * len(datos_con))
                            cur.execute(f"INSERT INTO consultas ({colsq}) VALUES ({valsq}) RETURNING id", list(datos_con.values()))
                            cid = cur.fetchone()[0]; st.session_state.consulta_id = cid
                        conn.commit(); cur.close(); conn.close()
                        st.success(f"✅ Consulta guardada (ID {cid})"); st.rerun()
                    except Exception as e: st.error(f"❌ Error al guardar consulta: {e}")
                if guardar_grad:
                    if st.session_state.consulta_id is None:
                        st.warning("⚠️ Primero guarda la consulta antes de enviar al laboratorio")
                    else:
                        tipo_id = int(tipos_df[tipos_df['nombre'] == tipo_sel]['id'].values[0]) if tipo_sel != "Seleccionar..." and not tipos_df.empty else None
                        mat_id = int(mat_df[mat_df['nombre'] == mat_sel]['id'].values[0]) if mat_sel != "Seleccionar..." and not mat_df.empty else None
                        trat_id = int(trat_df[trat_df['nombre'] == trat_sel]['id'].values[0]) if trat_sel != "Seleccionar..." and not trat_df.empty else None
                        lab_id = int(lab_df[lab_df['nombre'] == lab_sel]['id'].values[0]) if lab_sel != "Seleccionar..." and not lab_df.empty else None
                        datos_g = {
                            'consulta_id': st.session_state.consulta_id, 'paciente_id': paciente_id,
                            'rx_od_esf': rx['od_esf'], 'rx_od_cil': rx['od_cil'], 'rx_od_eje': int(rx['od_eje']), 'rx_od_prisma': rx['od_prisma'],
                            'rx_od_av_lejos': rx['od_avl'], 'rx_od_av_cerca': rx['od_avc'], 'rx_od_add': rx['od_add'], 'rx_od_tipo_lente': rx['od_tipo'],
                            'rx_oi_esf': rx['oi_esf'], 'rx_oi_cil': rx['oi_cil'], 'rx_oi_eje': int(rx['oi_eje']), 'rx_oi_prisma': rx['oi_prisma'],
                            'rx_oi_av_lejos': rx['oi_avl'], 'rx_oi_av_cerca': rx['oi_avc'], 'rx_oi_add': rx['oi_add'], 'rx_oi_tipo_lente': rx['oi_tipo'],
                            'tipo_lente_id': tipo_id, 'material_id': mat_id, 'tratamiento_id': trat_id, 'detalles_adicionales': detalles,
                            'fecha_pedido': fecha_pedido, 'laboratorio_id': lab_id, 'fecha_requerida': fecha_req, 'hora_requerida': hora_req,
                        }
                        try:
                            conn = get_connection(); cur = conn.cursor()
                            if g is not None:
                                sets = ', '.join([f"{k}=%s" for k in datos_g.keys() if k not in ('consulta_id', 'paciente_id')])
                                vals = [v for k, v in datos_g.items() if k not in ('consulta_id', 'paciente_id')] + [g['id']]
                                cur.execute(f"UPDATE graduaciones_lab SET {sets} WHERE id=%s", vals); gid = int(g['id'])
                            else:
                                colsq = ', '.join(datos_g.keys()); valsq = ', '.join(['%s'] * len(datos_g))
                                cur.execute(f"INSERT INTO graduaciones_lab ({colsq}) VALUES ({valsq}) RETURNING id", list(datos_g.values()))
                                gid = cur.fetchone()[0]
                            conn.commit(); cur.close(); conn.close()
                            st.success(f"✅ Graduación y pedido guardados (Pedido ID {gid})"); st.balloons(); st.rerun()
                        except Exception as e: st.error(f"❌ Error al guardar graduación: {e}")
                if generar_pdf:
                    if st.session_state.consulta_id is None:
                        st.warning("️ Guarda primero la consulta y su graduación")
                    else:
                        conn = get_connection()
                        gpdf = pd.read_sql("""
                            SELECT g.*, p.nombre || ' ' || p.apellidos as paciente, p.cedula, p.fecha_nacimiento,
                                   l.nombre as laboratorio, tl.nombre as tipo_lente, ml.nombre as material, tr.nombre as tratamiento
                            FROM graduaciones_lab g JOIN pacientes p ON g.paciente_id = p.id
                            LEFT JOIN laboratorios l ON g.laboratorio_id = l.id
                            LEFT JOIN tipos_lente tl ON g.tipo_lente_id = tl.id
                            LEFT JOIN materiales_lente ml ON g.material_id = ml.id
                            LEFT JOIN tratamientos tr ON g.tratamiento_id = tr.id
                            WHERE g.consulta_id = %s ORDER BY g.id DESC LIMIT 1
                        """, conn, params=(st.session_state.consulta_id,))
                        conn.close()
                        if gpdf.empty:
                            st.warning("️ Esta consulta aún no tiene graduación guardada")
                        else:
                            r = gpdf.iloc[0]
                            datos_pdf = {
                                'optica': OPTICA_CONFIG['nombre'], 'doctor': OPTICA_CONFIG['doctor'], 'subtitulo': OPTICA_CONFIG['subtitulo'],
                                'direccion': OPTICA_CONFIG['direccion'], 'telefono': OPTICA_CONFIG['telefono'],
                                'numero': f"{int(r['id']):03d}", 'fecha': pd.to_datetime(r['fecha_pedido']).strftime('%d/%m/%Y'),
                                'paciente': r['paciente'], 'edad': f"{calcular_edad(r['fecha_nacimiento']) or '—'} años", 'cedula': r['cedula'] or 'S/C',
                                'rx_od_esf': fmt_num(r['rx_od_esf']), 'rx_od_cil': fmt_num(r['rx_od_cil']), 'rx_od_eje': fmt_num(r['rx_od_eje']),
                                'rx_od_prisma': r['rx_od_prisma'] or '', 'rx_od_avl': r['rx_od_av_lejos'] or '', 'rx_od_avc': r['rx_od_av_cerca'] or '',
                                'rx_od_add': fmt_num(r['rx_od_add']), 'rx_od_tipo': r['rx_od_tipo_lente'] or '',
                                'rx_oi_esf': fmt_num(r['rx_oi_esf']), 'rx_oi_cil': fmt_num(r['rx_oi_cil']), 'rx_oi_eje': fmt_num(r['rx_oi_eje']),
                                'rx_oi_prisma': r['rx_oi_prisma'] or '', 'rx_oi_avl': r['rx_oi_av_lejos'] or '', 'rx_oi_avc': r['rx_oi_av_cerca'] or '',
                                'rx_oi_add': fmt_num(r['rx_oi_add']), 'rx_oi_tipo': r['rx_oi_tipo_lente'] or '',
                                'tipo_lente': r['tipo_lente'], 'material': r['material'], 'tratamiento': r['tratamiento'], 'detalles': r['detalles_adicionales'],
                                'laboratorio': r['laboratorio'], 'fecha_pedido': pd.to_datetime(r['fecha_pedido']).strftime('%d/%m/%Y'),
                                'fecha_requerida': r['fecha_requerida'] or '—', 'hora_requerida': r['hora_requerida'] or '—',
                                'hora': pd.to_datetime(r['fecha_creacion']).strftime('%I:%M %p'),
                            }
                            try:
                                pdf_bytes = generar_pdf_orden(datos_pdf)
                                st.success("✅ PDF generado. Descárgalo abajo.")
                                st.download_button("⬇️ Descargar PDF", data=pdf_bytes, file_name=f"Orden_{int(r['id']):03d}_{r['paciente'].replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True, key="con_pdf_dl")
                            except Exception as e:
                                st.error(f"❌ Error al generar PDF: {e}")
                if envio_pedido:
                    if st.session_state.consulta_id is None:
                        st.warning("️ Guarda primero la consulta y su graduación")
                    else:
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute("UPDATE graduaciones_lab SET estado_pedido = 'Enviado a Lab.' WHERE consulta_id = %s", (st.session_state.consulta_id,))
                        if cur.rowcount == 0:
                            st.warning("⚠️ No hay graduación guardada para enviar al laboratorio")
                        else:
                            st.success("✅ Pedido marcado como **Enviado a Lab.** — ya aparece en  Pedidos")
                        conn.commit(); cur.close(); conn.close()
                if eliminar_con:
                    if st.session_state.consulta_id is None:
                        st.warning("⚠️ No hay consulta seleccionada")
                    else:
                        if 'confirmar_del_con' not in st.session_state:
                            st.session_state.confirmar_del_con = True
                            st.warning("️ Presiona Eliminar de nuevo para confirmar (se borra consulta y pedido)")
                        else:
                            try:
                                conn = get_connection(); cur = conn.cursor()
                                cur.execute("DELETE FROM graduaciones_lab WHERE consulta_id = %s", (st.session_state.consulta_id,))
                                cur.execute("DELETE FROM consultas WHERE id = %s", (st.session_state.consulta_id,))
                                conn.commit(); cur.close(); conn.close()
                                st.session_state.consulta_id = None; del st.session_state.confirmar_del_con
                                st.success("✅ Consulta eliminada"); st.rerun()
                            except Exception as e: st.error(f"❌ Error al eliminar: {e}")
        with tab_pdf:
            st.subheader(" Generar PDF de Orden / Receta")
            st.info("💡 Selecciona una orden con graduación guardada y descarga el PDF listo para imprimir o enviar")
            conn = get_connection()
            pdf_df = pd.read_sql("""
                SELECT g.id, g.fecha_pedido, g.fecha_creacion, g.fecha_requerida, g.hora_requerida,
                       g.rx_od_esf, g.rx_od_cil, g.rx_od_eje, g.rx_od_prisma, g.rx_od_av_lejos, g.rx_od_av_cerca, g.rx_od_add, g.rx_od_tipo_lente,
                       g.rx_oi_esf, g.rx_oi_cil, g.rx_oi_eje, g.rx_oi_prisma, g.rx_oi_av_lejos, g.rx_oi_av_cerca, g.rx_oi_add, g.rx_oi_tipo_lente,
                       g.detalles_adicionales,
                       p.nombre || ' ' || p.apellidos as paciente, p.cedula, p.fecha_nacimiento,
                       l.nombre as laboratorio, tl.nombre as tipo_lente, ml.nombre as material, tr.nombre as tratamiento
                FROM graduaciones_lab g
                JOIN pacientes p ON g.paciente_id = p.id
                LEFT JOIN laboratorios l ON g.laboratorio_id = l.id
                LEFT JOIN tipos_lente tl ON g.tipo_lente_id = tl.id
                LEFT JOIN materiales_lente ml ON g.material_id = ml.id
                LEFT JOIN tratamientos tr ON g.tratamiento_id = tr.id
                ORDER BY g.id DESC
            """, conn)
            conn.close()
            if pdf_df.empty:
                st.warning(" No hay graduaciones guardadas. Crea una en: Consulta → 🔬 Graduación y Envío a Lab → Guardar Graduación.")
            else:
                opc_pdf = [f"Orden {int(r['id']):03d} – {r['paciente']} – {pd.to_datetime(r['fecha_pedido']).strftime('%d/%m/%Y')}" for _, r in pdf_df.iterrows()]
                sel_pdf = st.selectbox("📋 Selecciona la orden a imprimir:", opc_pdf, key="pdf_sel")
                row = pdf_df.iloc[opc_pdf.index(sel_pdf)]
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Paciente:** {row['paciente']}")
                    st.markdown(f"**Cédula:** {row['cedula'] or 'S/C'}")
                    st.markdown(f"**Edad:** {calcular_edad(row['fecha_nacimiento']) or '—'} años")
                with c2:
                    st.markdown(f"**Laboratorio:** {row['laboratorio'] or '—'}")
                    st.markdown(f"**Lente:** {row['tipo_lente'] or '—'} / {row['material'] or '—'}")
                    st.markdown(f"**Tratamiento:** {row['tratamiento'] or '—'}")
                if st.button(" Generar PDF", type="primary", use_container_width=True, key="pdf_gen"):
                    datos_pdf = {
                        'optica': OPTICA_CONFIG['nombre'], 'doctor': OPTICA_CONFIG['doctor'], 'subtitulo': OPTICA_CONFIG['subtitulo'],
                        'direccion': OPTICA_CONFIG['direccion'], 'telefono': OPTICA_CONFIG['telefono'],
                        'numero': f"{int(row['id']):03d}", 'fecha': pd.to_datetime(row['fecha_pedido']).strftime('%d/%m/%Y'),
                        'paciente': row['paciente'], 'edad': f"{calcular_edad(row['fecha_nacimiento']) or '—'} años", 'cedula': row['cedula'] or 'S/C',
                        'rx_od_esf': fmt_num(row['rx_od_esf']), 'rx_od_cil': fmt_num(row['rx_od_cil']), 'rx_od_eje': fmt_num(row['rx_od_eje']),
                        'rx_od_prisma': row['rx_od_prisma'] or '', 'rx_od_avl': row['rx_od_av_lejos'] or '', 'rx_od_avc': row['rx_od_av_cerca'] or '',
                        'rx_od_add': fmt_num(row['rx_od_add']), 'rx_od_tipo': row['rx_od_tipo_lente'] or '',
                        'rx_oi_esf': fmt_num(row['rx_oi_esf']), 'rx_oi_cil': fmt_num(row['rx_oi_cil']), 'rx_oi_eje': fmt_num(row['rx_oi_eje']),
                        'rx_oi_prisma': row['rx_oi_prisma'] or '', 'rx_oi_avl': row['rx_oi_av_lejos'] or '', 'rx_oi_avc': row['rx_oi_av_cerca'] or '',
                        'rx_oi_add': fmt_num(row['rx_oi_add']), 'rx_oi_tipo': row['rx_oi_tipo_lente'] or '',
                        'tipo_lente': row['tipo_lente'], 'material': row['material'], 'tratamiento': row['tratamiento'], 'detalles': row['detalles_adicionales'],
                        'laboratorio': row['laboratorio'], 'fecha_pedido': pd.to_datetime(row['fecha_pedido']).strftime('%d/%m/%Y'),
                        'fecha_requerida': row['fecha_requerida'] or '—', 'hora_requerida': row['hora_requerida'] or '—',
                        'hora': pd.to_datetime(row['fecha_creacion']).strftime('%I:%M %p'),
                    }
                    try:
                        pdf_bytes = generar_pdf_orden(datos_pdf)
                        st.success("✅ PDF generado. Haz click abajo para descargarlo.")
                        st.download_button("⬇️ Descargar PDF", data=pdf_bytes, file_name=f"Orden_{int(row['id']):03d}_{row['paciente'].replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True, key="pdf_dl")
                    except Exception as e:
                        st.error(f"❌ Error al generar el PDF: {e}")

    # ═══════════════════════════════════════════════════════
    #  GESTIÓN DE PEDIDOS | VENTAS | COBROS
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "pedidos":
        st.title(" Gestión de Pedidos | Ventas | Cobros")
        conn = get_connection()
        ped_df = pd.read_sql("""
            SELECT g.id, g.paciente_id, g.fecha_pedido, g.estado_pedido, g.venta_registrada, g.total_venta,
                   p.nombre || ' ' || p.apellidos as paciente, p.cedula, p.sexo, p.telefono, p.email, p.direccion,
                   COALESCE((SELECT SUM(c.monto) FROM cobros c WHERE c.graduacion_id = g.id), 0) as abonado
            FROM graduaciones_lab g JOIN pacientes p ON g.paciente_id = p.id
            ORDER BY g.id DESC
        """, conn)
        est_df = pd.read_sql("SELECT nombre FROM estados_pedido WHERE activo = TRUE ORDER BY nombre", conn)
        conn.close()
        tab_ped, tab_cob, tab_ven = st.tabs([" Pedidos y Ventas", "💵 Cobros / Abonos", "💰 Registrar Venta"])
        
        with tab_ped:
            with st.expander("🔎 Filtros", expanded=True):
                f1, f2, f3, f4, f5, f6 = st.columns([2, 2, 3, 2, 2, 2])
                with f1: f_inicio = st.date_input("Fecha Inicio", value=None, key="ped_f_ini")
                with f2: f_fin = st.date_input("Fecha Fin", value=None, key="ped_f_fin")
                with f3: f_estado = st.selectbox("Estado", ["Todos"] + est_df['nombre'].tolist(), key="ped_f_est")
                with f4: f_venta = st.radio("Venta Registrada", ["Todos", "Sí", "No"], horizontal=True, key="ped_f_venta")
                with f5: f_cobro = st.radio("Pendiente de cobro", ["Todos", "Sí", "No"], horizontal=True, key="ped_f_cobro")
                with f6:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚫 Quitar Filtros", use_container_width=True, key="ped_f_clear"):
                        st.session_state.ped_f_ini = None; st.session_state.ped_f_fin = None
                        st.session_state.ped_f_est = "Todos"; st.session_state.ped_f_venta = "Todos"; st.session_state.ped_f_cobro = "Todos"
                        st.rerun()
            dfv = ped_df.copy()
            dfv['pendiente'] = dfv['total_venta'] - dfv['abonado']
            if f_inicio: dfv = dfv[pd.to_datetime(dfv['fecha_pedido']).dt.date >= f_inicio]
            if f_fin: dfv = dfv[pd.to_datetime(dfv['fecha_pedido']).dt.date <= f_fin]
            if f_estado != "Todos": dfv = dfv[dfv['estado_pedido'] == f_estado]
            if f_venta == "Sí": dfv = dfv[dfv['venta_registrada'] == True]
            if f_venta == "No": dfv = dfv[dfv['venta_registrada'] == False]
            if f_cobro == "Sí": dfv = dfv[dfv['pendiente'] > 0]
            if f_cobro == "No": dfv = dfv[dfv['pendiente'] <= 0]
            if not dfv.empty:
                dfv_show = dfv.copy()
                dfv_show.insert(0, 'n_orden', [f"N°-{int(i):03d}" for i in dfv_show['id']])
                dfv_show['fecha'] = pd.to_datetime(dfv_show['fecha_pedido']).dt.strftime('%d/%m/%Y')
                dfv_show['venta'] = dfv_show['venta_registrada'].map({True: 'Sí', False: 'No'})
                st.dataframe(dfv_show[['n_orden', 'fecha', 'paciente', 'estado_pedido', 'venta', 'total_venta', 'abonado', 'pendiente']]
                             .rename(columns={'n_orden': 'N° Orden', 'fecha': 'Fecha', 'paciente': 'Paciente', 'estado_pedido': 'Estado',
                                              'venta': 'Venta Registrada', 'total_venta': 'Total Venta', 'abonado': 'Abonado', 'pendiente': 'Pendiente'}),
                             use_container_width=True, height=300)
                st.markdown("---")
                opc = [f"N°-{int(r['id']):03d} – {r['paciente']} – {pd.to_datetime(r['fecha_pedido']).strftime('%d/%m/%Y')}" for _, r in dfv.iterrows()]
                sel = st.selectbox("📦 Pedido seleccionado:", opc, key="ped_sel_row")
                row = dfv.iloc[opc.index(sel)]
                gid = int(row['id'])
                a1, a2, a3 = st.columns(3)
                with a1:
                    st.markdown("**🔄 Cambiar Estado**")
                    opc_est = est_df['nombre'].tolist()
                    nuevo_est = st.selectbox("Estado", opc_est, index=opc_est.index(row['estado_pedido']) if row['estado_pedido'] in opc_est else 0, key="ped_new_est")
                    if st.button("💾 Actualizar Estado", use_container_width=True, key="ped_upd_est"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute("UPDATE graduaciones_lab SET estado_pedido = %s WHERE id = %s", (nuevo_est, gid))
                        conn.commit(); cur.close(); conn.close()
                        st.success("✅ Estado actualizado"); st.rerun()
                with a2:
                    st.markdown("**💰 Registrar Venta**")
                    total_v = st.number_input("Total Venta $", min_value=0.0, step=0.01, value=float(row['total_venta'] or 0), key="ped_total_v")
                    if st.button("💰 Guardar Venta", use_container_width=True, key="ped_reg_venta"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute("UPDATE graduaciones_lab SET total_venta = %s, venta_registrada = TRUE WHERE id = %s", (total_v, gid))
                        conn.commit(); cur.close(); conn.close()
                        st.success("✅ Venta registrada"); st.rerun()
                with a3:
                    st.markdown("**🗑️ Eliminar Pedido**")
                    st.info(f"Abonado: ${row['abonado']} | Pendiente: ${row['pendiente']}")
                    if st.button("🗑️ Eliminar", use_container_width=True, key="ped_del"):
                        if st.session_state.get('conf_del_ped') == gid:
                            conn = get_connection(); cur = conn.cursor()
                            cur.execute("DELETE FROM graduaciones_lab WHERE id = %s", (gid,))
                            conn.commit(); cur.close(); conn.close()
                            st.session_state.conf_del_ped = None
                            st.success("✅ Pedido eliminado"); st.rerun()
                        else:
                            st.session_state.conf_del_ped = gid
                            st.warning("⚠️ Presiona Eliminar de nuevo para confirmar")
            else:
                st.info("📭 No hay pedidos que coincidan. Crea uno en 🩺 Consultas →  Graduación y Envío a Lab.")
        
        with tab_cob:
            st.subheader(" Control de Cobros, Abonos y Cancelaciones")
            ventas_df = ped_df[ped_df['venta_registrada'] == True]
            if ventas_df.empty:
                st.warning("⚠️ Primero registra una venta (pestaña 💰 Registrar Venta o botón 💰 Guardar Venta).")
            else:
                opc_v = [f"N°-{int(r['id']):03d} – {r['paciente']} – Total ${float(r['total_venta'] or 0):.2f}" for _, r in ventas_df.iterrows()]
                sel_v = st.selectbox("🧾 Corresponde a la Venta:", opc_v, key="cob_sel_venta")
                vrow = ventas_df.iloc[opc_v.index(sel_v)]
                gid = int(vrow['id'])
                total = float(vrow['total_venta'] or 0)
                c_izq, c_der = st.columns([1, 2])
                with c_izq:
                    st.markdown("#### 📋 Corresponde a Venta:")
                    st.markdown(f"**Fecha:** {pd.to_datetime(vrow['fecha_pedido']).strftime('%d/%m/%Y')}")
                    st.markdown(f"**Cédula:** {vrow['cedula'] or 'S/C'}")
                    st.markdown(f"**Nombres:** {vrow['paciente']}")
                    st.markdown(f"**Sexo:** {vrow['sexo'] or '—'}")
                    st.markdown(f"**Teléfono:** {vrow['telefono'] or '—'}")
                    st.markdown(f"**Email:** {vrow['email'] or '—'}")
                    st.markdown(f"**Dir.:** {vrow['direccion'] or '—'}")
                    conn = get_connection()
                    it = pd.read_sql("""
                        SELECT tl.nombre as tipo, ml.nombre as material, tr.nombre as tratamiento, l.nombre as laboratorio
                        FROM graduaciones_lab g
                        LEFT JOIN tipos_lente tl ON g.tipo_lente_id = tl.id
                        LEFT JOIN materiales_lente ml ON g.material_id = ml.id
                        LEFT JOIN tratamientos tr ON g.tratamiento_id = tr.id
                        LEFT JOIN laboratorios l ON g.laboratorio_id = l.id
                        WHERE g.id = %s
                    """, conn, params=(gid,))
                    conn.close()
                    st.markdown("---")
                    if not it.empty:
                        r0 = it.iloc[0]
                        st.markdown(f"**Cantidad: 1** – Lente {r0['tipo'] or '—'} / {r0['material'] or '—'} / {r0['tratamiento'] or '—'}")
                        st.markdown(f"**Cantidad: 1** – Servicio de laboratorio: {r0['laboratorio'] or '—'}")
                with c_der:
                    st.markdown("#### 🧾 Historial de Cobros")
                    conn = get_connection()
                    cob_df = pd.read_sql("SELECT id, fecha_cobro, monto, metodo, nota FROM cobros WHERE graduacion_id = %s ORDER BY fecha_cobro, id", conn, params=(gid,))
                    conn.close()
                    abonado = float(cob_df['monto'].sum()) if not cob_df.empty else 0.0
                    saldo = total - abonado
                    if not cob_df.empty:
                        show = cob_df.copy()
                        show['total_venta'] = total
                        show['saldo_pendiente'] = total - show['monto'].cumsum()
                        show['fecha_cobro'] = pd.to_datetime(show['fecha_cobro']).dt.strftime('%d/%m/%Y')
                        st.dataframe(show[['fecha_cobro', 'total_venta', 'monto', 'saldo_pendiente', 'nota', 'metodo']]
                                     .rename(columns={'fecha_cobro': 'Fecha', 'total_venta': 'Total Venta', 'monto': 'Abono',
                                                      'saldo_pendiente': 'Saldo Pendiente', 'nota': 'Concepto', 'metodo': 'Método'}),
                                     use_container_width=True, height=250)
                    else:
                        st.info("Sin cobros registrados para esta venta.")
                st.markdown("---")
                st.markdown("#### 💰 Realizar Cobro")
                r1, r2, r3, r4, r5, r6 = st.columns([1.2, 1.2, 1.2, 2, 1.4, 1.2])
                with r1:
                    st.markdown("**Saldo Pendiente**")
                    st.markdown(f"### ${saldo:.2f}")
                with r2:
                    abono = st.number_input("Abono", min_value=0.0, step=0.01, key="cob_abono")
                with r3:
                    st.markdown("**Nuevo Saldo**")
                    st.markdown(f"### ${saldo - abono:.2f}")
                with r4:
                    concepto = st.text_input("Concepto", key="cob_concepto", placeholder="Ej: primer pago")
                with r5:
                    metodo_cob = st.selectbox("Método", ["Efectivo", "Punto de Venta", "Transferencia", "Pago Móvil", "Zelle"], key="cob_metodo")
                with r6:
                    fecha_cob = st.date_input("Fecha", value=date.today(), key="cob_fecha")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("💾 Guardar Cobro", type="primary", use_container_width=True, key="cob_guardar"):
                        if abono <= 0:
                            st.warning("️ El abono debe ser mayor a 0")
                        elif abono > saldo:
                            st.warning("️ El abono supera el saldo pendiente")
                        else:
                            conn = get_connection(); cur = conn.cursor()
                            cur.execute("INSERT INTO cobros (graduacion_id, paciente_id, monto, metodo, nota, fecha_cobro) VALUES (%s,%s,%s,%s,%s,%s)",
                                        (gid, int(vrow['paciente_id']), abono, metodo_cob, concepto, fecha_cob))
                            conn.commit(); cur.close(); conn.close()
                            st.success(f"✅ Abono de ${abono:.2f} registrado")
                            st.rerun()
                with cc2:
                    if not cob_df.empty:
                        opc_an = [f"{pd.to_datetime(r['fecha_cobro']).strftime('%d/%m/%Y')} – ${float(r['monto']):.2f} – {r['nota'] or r['metodo']}" for _, r in cob_df.iterrows()]
                        sel_an = st.selectbox("🗑️ Anular cobro (cancelación):", opc_an, key="cob_sel_anular")
                        if st.button("🗑️ Anular Cobro", use_container_width=True, key="cob_anular"):
                            cid_an = int(cob_df.iloc[opc_an.index(sel_an)]['id'])
                            if st.session_state.get('conf_anular_cobro') == cid_an:
                                conn = get_connection(); cur = conn.cursor()
                                cur.execute("DELETE FROM cobros WHERE id = %s", (cid_an,))
                                conn.commit(); cur.close(); conn.close()
                                st.session_state.conf_anular_cobro = None
                                st.success("✅ Cobro anulado: el saldo se recalculó")
                                st.rerun()
                            else:
                                st.session_state.conf_anular_cobro = cid_an
                                st.warning("⚠️ Presiona de nuevo para confirmar la anulación")
        
        with tab_ven:
            st.subheader("💰 Registrar Venta")
            if 'carrito' not in st.session_state: st.session_state.carrito = []
            if ped_df.empty:
                st.info("📭 No hay pedidos. Crea uno en 🩺 Consultas → 🔬 Graduación y Envío a Lab.")
            else:
                opc_pv = [f"N°-{int(r['id']):03d} – {r['paciente']}" for _, r in ped_df.iterrows()]
                sel_pv = st.selectbox("🧾 Venta corresponde al pedido:", opc_pv, key="ven_sel_pedido")
                prow = ped_df.iloc[opc_pv.index(sel_pv)]
                pid_pedido = int(prow['id']); pac_id = int(prow['paciente_id'])
                if st.session_state.get('carrito_pedido') != pid_pedido:
                    st.session_state.carrito = []
                    st.session_state.carrito_pedido = pid_pedido
                conn = get_connection()
                rx = pd.read_sql("SELECT rx_od_esf, rx_od_cil, rx_od_eje, rx_od_prisma, rx_od_av_lejos, rx_od_av_cerca, rx_od_add, rx_od_tipo_lente, rx_oi_esf, rx_oi_cil, rx_oi_eje FROM graduaciones_lab WHERE id = %s", conn, params=(pid_pedido,))
                pac = pd.read_sql("SELECT cedula, nombre, apellidos, sexo, telefono, email FROM pacientes WHERE id = %s", conn, params=(pac_id,))
                conn.close()
                st.markdown("#### 📋 Venta corresponde a:")
                c_rx, c_pac = st.columns([2, 1])
                with c_rx:
                    if not rx.empty:
                        r0 = rx.iloc[0]
                        st.markdown(f"**Orden N°-{pid_pedido:03d}**")
                        st.markdown("| Ojo | Esfera | Cilindro | Eje | Prisma | AV Lejos | AV Cerca | ADD | Tipo Lente |")
                        st.markdown("|---|---|---|---|---|---|---|---|---|")
                        st.markdown(f"| OD | {fmt_num(r0['rx_od_esf'])} | {fmt_num(r0['rx_od_cil'])} | {fmt_num(r0['rx_od_eje'])} | {r0['rx_od_prisma'] or ''} | {r0['rx_od_av_lejos'] or ''} | {r0['rx_od_av_cerca'] or ''} | {fmt_num(r0['rx_od_add'])} | {r0['rx_od_tipo_lente'] or ''} |")
                        st.markdown(f"| OI | {fmt_num(r0['rx_oi_esf'])} | {fmt_num(r0['rx_oi_cil'])} | {fmt_num(r0['rx_oi_eje'])} | {r0['rx_oi_prisma'] or ''} | {r0['rx_oi_av_lejos'] or ''} | {r0['rx_oi_av_cerca'] or ''} | | |")
                    else:
                        st.info("Sin Rx en este pedido")
                with c_pac:
                    if not pac.empty:
                        p0 = pac.iloc[0]
                        st.markdown(f"**Cédula:** {p0['cedula'] or 'S/C'}")
                        st.markdown(f"**Nombres:** {p0['nombre']} {p0['apellidos']}")
                        st.markdown(f"**Sexo:** {p0['sexo'] or '—'}")
                        st.markdown(f"**Teléfono:** {p0['telefono'] or '—'}")
                        st.markdown(f"**Email:** {p0['email'] or '—'}")
                st.markdown("####  Datos del Producto")
                busc = st.text_input("Buscador:", key="ven_busc")
                conn = get_connection()
                if busc:
                    prods = pd.read_sql("SELECT id, sku, nombre, stock_actual, precio_venta FROM productos WHERE activo = TRUE AND (nombre ILIKE %s OR sku ILIKE %s) ORDER BY nombre", conn, params=(f'%{busc}%', f'%{busc}%'))
                else:
                    prods = pd.read_sql("SELECT id, sku, nombre, stock_actual, precio_venta FROM productos WHERE activo = TRUE ORDER BY nombre LIMIT 50", conn)
                conn.close()
                if prods.empty:
                    st.warning("📭 No hay productos. Regístralos en 📦 Inventario.")
                else:
                    opc_prod = [f"{r['nombre']} ({r['sku']}) – Stock: {int(r['stock_actual'])}" for _, r in prods.iterrows()]
                    sel_prod = st.selectbox("Descripción del producto | Existencias", opc_prod, key="ven_sel_prod")
                    prow2 = prods.iloc[opc_prod.index(sel_prod)]
                    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.2])
                    with c1: precio_u = st.number_input("Precio", min_value=0.0, step=0.01, value=float(prow2['precio_venta'] or 0), key="ven_precio")
                    with c2: cant = st.number_input("Cant.", min_value=1, step=1, value=1, key="ven_cant")
                    with c3: descto = st.number_input("Descto %", min_value=0.0, max_value=100.0, step=0.5, value=0.0, key="ven_descto")
                    with c4:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🛒 Añadir", use_container_width=True, key="ven_add"):
                            if cant > int(prow2['stock_actual']):
                                st.error(f"❌ Stock insuficiente (disponible: {int(prow2['stock_actual'])})")
                            else:
                                linea = {'producto_id': int(prow2['id']), 'sku': prow2['sku'], 'descripcion': prow2['nombre'],
                                         'cantidad': int(cant), 'precio_unitario': float(precio_u), 'descuento_pct': float(descto),
                                         'total': round(cant * precio_u * (1 - descto / 100.0), 2)}
                                st.session_state.carrito = st.session_state.carrito + [linea]
                                st.rerun()
                carrito = st.session_state.carrito
                if carrito:
                    dfc = pd.DataFrame(carrito)
                    st.dataframe(dfc[['sku', 'descripcion', 'cantidad', 'precio_unitario', 'descuento_pct', 'total']]
                                 .rename(columns={'sku': 'ID', 'descripcion': 'Descripción del producto', 'cantidad': 'Cant.',
                                                  'precio_unitario': 'Precio Unitario', 'descuento_pct': 'Descto.', 'total': 'Total'}),
                                 use_container_width=True, height=200)
                    opc_q = [f"{i+1}. {l['descripcion']} x{l['cantidad']}" for i, l in enumerate(carrito)]
                    cq1, cq2 = st.columns([3, 1])
                    with cq1: sel_q = st.selectbox("Quitar línea:", opc_q, key="ven_sel_q")
                    with cq2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🗑️ Quitar", use_container_width=True, key="ven_quitar"):
                            carrito.pop(opc_q.index(sel_q))
                            st.session_state.carrito = carrito
                            st.rerun()
                st.markdown("---")
                subtotal = sum(l['total'] for l in carrito)
                t1, t2, t3, t4 = st.columns(4)
                with t1: st.markdown(f"**Sub Total**\n### ${subtotal:.2f}")
                with t2:
                    iva_pct = st.number_input("IVA %", min_value=0.0, step=0.5, value=15.0, key="ven_iva")
                    iva_monto = round(subtotal * iva_pct / 100.0, 2)
                    st.markdown(f"**IVA**\n### ${iva_monto:.2f}")
                with t3:
                    total = round(subtotal + iva_monto, 2)
                    st.markdown(f"**Total**\n### ${total:.2f}")
                with t4:
                    abono_v = st.number_input("Abono", min_value=0.0, step=0.01, key="ven_abono")
                    st.markdown(f"**Pendiente**\n### ${total - abono_v:.2f}")
                c1, c2, c3 = st.columns([2, 1.4, 1.2])
                with c1: concepto_v = st.text_input("Concepto", key="ven_concepto")
                with c2: metodo_v = st.selectbox("Método (abono)", ["Efectivo", "Punto de Venta", "Transferencia", "Pago Móvil", "Zelle"], key="ven_metodo")
                with c3: fecha_v = st.date_input("Fecha", value=date.today(), key="ven_fecha")
                if st.button("💾 Guardar Venta", type="primary", use_container_width=True, key="ven_guardar"):
                    if not carrito:
                        st.warning("⚠️ Añade al menos un producto a la venta")
                    elif abono_v > total:
                        st.warning("️ El abono no puede superar el total")
                    else:
                        try:
                            conn = get_connection(); cur = conn.cursor()
                            cur.execute("""
                                INSERT INTO ventas (pedido_id, paciente_id, fecha_venta, subtotal, iva_pct, iva_monto, total, concepto)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                            """, (pid_pedido, pac_id, fecha_v, subtotal, iva_pct, iva_monto, total, concepto_v))
                            venta_id = cur.fetchone()[0]
                            for l in carrito:
                                cur.execute("""
                                    INSERT INTO venta_detalles (venta_id, producto_id, descripcion, cantidad, precio_unitario, descuento_pct, total)
                                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                                """, (venta_id, l['producto_id'], l['descripcion'], l['cantidad'], l['precio_unitario'], l['descuento_pct'], l['total']))
                                cur.execute("UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s", (l['cantidad'], l['producto_id']))
                                # Descontar de la ubicación principal
                                cur.execute("""
                                    UPDATE stock_ubicaciones SET cantidad = cantidad - %s
                                    WHERE producto_id = %s AND cantidad >= %s
                                    LIMIT 1
                                """, (l['cantidad'], l['producto_id'], l['cantidad']))
                            cur.execute("UPDATE graduaciones_lab SET venta_registrada = TRUE, total_venta = %s WHERE id = %s", (total, pid_pedido))
                            if abono_v > 0:
                                cur.execute("""
                                    INSERT INTO cobros (graduacion_id, paciente_id, monto, metodo, nota, fecha_cobro, venta_id)
                                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                                """, (pid_pedido, pac_id, abono_v, metodo_v, f"Abono inicial venta V-{venta_id:03d}", fecha_v, venta_id))
                            conn.commit(); cur.close(); conn.close()
                            st.session_state.carrito = []
                            st.success(f"✅ Venta **V-{venta_id:03d}** guardada por **${total:.2f}** (inventario descontado)")
                            st.balloons(); st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar venta: {e}")
                st.markdown("---")
                st.markdown("####  Ventas de este pedido")
                conn = get_connection()
                vlist = pd.read_sql("SELECT id, fecha_venta, total, concepto, estado FROM ventas WHERE pedido_id = %s ORDER BY id", conn, params=(pid_pedido,))
                conn.close()
                if not vlist.empty:
                    for _, v in vlist.iterrows():
                        vid = int(v['id'])
                        with st.expander(f"V-{vid:03d} – {pd.to_datetime(v['fecha_venta']).strftime('%d/%m/%Y')} – ${float(v['total']):.2f} ({v['estado']})"):
                            conn = get_connection()
                            det = pd.read_sql("SELECT descripcion, cantidad, precio_unitario, descuento_pct, total FROM venta_detalles WHERE venta_id = %s", conn, params=(vid,))
                            conn.close()
                            st.dataframe(det, use_container_width=True)
                            if v['estado'] == 'VIGENTE':
                                if st.button(f"🗑️ Anular venta V-{vid:03d}", key=f"ven_anular_{vid}"):
                                    if st.session_state.get('conf_anular_venta') == vid:
                                        conn = get_connection(); cur = conn.cursor()
                                        cur.execute("SELECT producto_id, cantidad FROM venta_detalles WHERE venta_id = %s", (vid,))
                                        for pid_p, cant_p in cur.fetchall():
                                            if pid_p: cur.execute("UPDATE productos SET stock_actual = stock_actual + %s WHERE id = %s", (cant_p, pid_p))
                                        cur.execute("DELETE FROM cobros WHERE venta_id = %s", (vid,))
                                        cur.execute("UPDATE ventas SET estado = 'ANULADA' WHERE id = %s", (vid,))
                                        cur.execute("SELECT COALESCE(SUM(total),0) FROM ventas WHERE pedido_id = %s AND estado = 'VIGENTE'", (pid_pedido,))
                                        suma_vig = cur.fetchone()[0]
                                        cur.execute("UPDATE graduaciones_lab SET total_venta = %s, venta_registrada = %s WHERE id = %s", (suma_vig, suma_vig > 0, pid_pedido))
                                        conn.commit(); cur.close(); conn.close()
                                        st.session_state.conf_anular_venta = None
                                        st.success("✅ Venta anulada: stock repuesto y abonos eliminados")
                                        st.rerun()
                                    else:
                                        st.session_state.conf_anular_venta = vid
                                        st.warning("⚠️ Presiona de nuevo para confirmar la anulación")
                else:
                    st.info("Sin ventas registradas para este pedido.")

    # ══════════════════════════════════════════════════════
    # 📦 INVENTARIO - CON DISTRIBUCIÓN POR UBICACIÓN
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "inventario":
        st.title("📦 Inventario - Master de Productos")
        tab_prod, tab_dist, tab_cons = st.tabs(["📦 Productos", "📍 Distribución por Ubicación", "🔍 Consulta por Ubicación"])
        
        with tab_prod:
            st.subheader("Registrar Nuevo Producto")
            conn = get_connection()
            cats_df = pd.read_sql("SELECT id, nombre FROM categorias ORDER BY nombre", conn)
            tipos_df = pd.read_sql("SELECT id, nombre FROM tipos_lente WHERE activo = TRUE ORDER BY nombre", conn)
            mat_df = pd.read_sql("SELECT id, nombre FROM materiales_lente WHERE activo = TRUE ORDER BY nombre", conn)
            trat_df = pd.read_sql("SELECT id, nombre FROM tratamientos WHERE activo = TRUE ORDER BY nombre", conn)
            lab_df = pd.read_sql("SELECT id, nombre FROM laboratorios WHERE activo = TRUE ORDER BY nombre", conn)
            prov_df = pd.read_sql("SELECT id, nombre FROM proveedores WHERE activo = TRUE ORDER BY nombre", conn)
            ubi_df = pd.read_sql("SELECT id, nombre FROM ubicaciones WHERE activo = TRUE ORDER BY nombre", conn)
            imp_df = pd.read_sql("SELECT id, nombre, tasa FROM impuestos WHERE activo = TRUE ORDER BY nombre", conn); conn.close()
            with st.form("form_nuevo_producto"):
                c1, c2, c3 = st.columns([3, 3, 2])
                with c1:
                    sku = st.text_input("SKU / Código *", key="prod_sku"); nombre_prod = st.text_input("Nombre *", key="prod_nombre")
                    marca = st.text_input("Marca", key="prod_marca"); modelo = st.text_input("Modelo", key="prod_modelo")
                with c2:
                    color = st.text_input("Color", key="prod_color"); genero = st.selectbox("Género", ["Unisex", "Masculino", "Femenino"], key="prod_genero")
                    cat_sel = st.selectbox("Categoría", ["Seleccionar..."] + cats_df['nombre'].tolist(), key="prod_cat")
                    tipo_sel = st.selectbox("🔍 Tipo de Lente", ["Seleccionar..."] + tipos_df['nombre'].tolist(), key="prod_tipo")
                with c3:
                    st.markdown("####  Imagen del Producto")
                    foto = st.file_uploader("Sube una foto (png, jpg, jpeg)", type=["png", "jpg", "jpeg"], key="prod_foto")
                    if foto is not None: st.image(foto, caption="Vista previa", use_container_width=True)
                st.markdown("#### 🔧 Selección de Lente y Materiales")
                c1, c2, c3, c4 = st.columns(4)
                with c1: mat_sel = st.selectbox("🧪 Material del Lente", ["Seleccionar..."] + mat_df['nombre'].tolist(), key="prod_mat")
                with c2: trat_sel = st.selectbox("✨ Tratamiento", ["Seleccionar..."] + trat_df['nombre'].tolist(), key="prod_trat")
                with c3: lab_sel = st.selectbox(" Laboratorio", ["Seleccionar..."] + lab_df['nombre'].tolist(), key="prod_lab")
                with c4: ubi_sel = st.selectbox(" Ubicación Principal", ["Seleccionar..."] + ubi_df['nombre'].tolist(), key="prod_ubi")
                c1, c2 = st.columns(2)
                with c1: prov_sel = st.selectbox("🚚 Proveedor", ["Seleccionar..."] + prov_df['nombre'].tolist(), key="prod_prov")
                st.markdown("#### 💰 Precio de Venta y Stock")
                c1, c2, c3 = st.columns(3)
                with c1: precio_venta = st.number_input("Precio Venta $", min_value=0.0, step=0.01, key="prod_pv")
                with c2: stock_ini = st.number_input("Stock Inicial (total)", min_value=0, step=1, key="prod_st")
                with c3: stock_min = st.number_input("Stock Mínimo", min_value=0, step=1, value=5, key="prod_sm")
                st.markdown("#### 🧾 Uso, Costo Unitario e Impuesto")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown("**Uso**")
                    uso_venta = st.checkbox("Venta", value=True, key="prod_uso_venta"); uso_compra = st.checkbox("Compra", value=True, key="prod_uso_compra")
                with c2: costo_bs = st.number_input("Costo Unitario Bs", min_value=0.0, step=0.01, key="prod_cbs")
                with c3: costo_usd = st.number_input("Costo Unitario US$", min_value=0.0, step=0.01, key="prod_cusd")
                with c4:
                    imp_sel = st.selectbox("Impuesto por Producto", ["Seleccionar..."] + imp_df['nombre'].tolist(), key="prod_imp")
                    if imp_sel != "Seleccionar...": st.info(f"Tasa: **{float(imp_df[imp_df['nombre'] == imp_sel]['tasa'].values[0])}%**")
                if st.form_submit_button("💾 Guardar Producto", type="primary", use_container_width=True):
                    if sku and nombre_prod:
                        try:
                            cat_id = int(cats_df[cats_df['nombre'] == cat_sel]['id'].values[0]) if cat_sel != "Seleccionar..." else None
                            tipo_id = int(tipos_df[tipos_df['nombre'] == tipo_sel]['id'].values[0]) if tipo_sel != "Seleccionar..." else None
                            mat_id = int(mat_df[mat_df['nombre'] == mat_sel]['id'].values[0]) if mat_sel != "Seleccionar..." else None
                            trat_id = int(trat_df[trat_df['nombre'] == trat_sel]['id'].values[0]) if trat_sel != "Seleccionar..." else None
                            lab_id = int(lab_df[lab_df['nombre'] == lab_sel]['id'].values[0]) if lab_sel != "Seleccionar..." else None
                            prov_id = int(prov_df[prov_df['nombre'] == prov_sel]['id'].values[0]) if prov_sel != "Seleccionar..." else None
                            ubi_id = int(ubi_df[ubi_df['nombre'] == ubi_sel]['id'].values[0]) if ubi_sel != "Seleccionar..." else None
                            imp_id = int(imp_df[imp_df['nombre'] == imp_sel]['id'].values[0]) if imp_sel != "Seleccionar..." else None
                            foto_url = None
                            if foto is not None:
                                ext = os.path.splitext(foto.name)[1].lower()
                                foto_nombre = f"{sku}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
                                with open(os.path.join(IMAGENES_DIR, foto_nombre), "wb") as f: f.write(foto.getbuffer())
                                foto_url = f"img/productos/{foto_nombre}"
                            conn = get_connection(); cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO productos (sku, nombre, categoria_id, marca, modelo, color, genero, precio_venta, stock_actual, stock_minimo, foto_url,
                                tipo_lente_id, material_id, tratamiento_id, laboratorio_id, proveedor_id, ubicacion_id,
                                uso_venta, uso_compra, costo_unitario_bs, costo_unitario_usd, impuesto_id)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                            """, (sku, nombre_prod, cat_id, marca, modelo, color, genero, precio_venta, stock_ini, stock_min, foto_url,
                                  tipo_id, mat_id, trat_id, lab_id, prov_id, ubi_id, uso_venta, uso_compra, costo_bs, costo_usd, imp_id))
                            prod_id = cursor.fetchone()[0]
                            if stock_ini > 0 and ubi_id:
                                cursor.execute("""
                                    INSERT INTO stock_ubicaciones (producto_id, ubicacion_id, cantidad)
                                    VALUES (%s, %s, %s)
                                    ON CONFLICT (producto_id, ubicacion_id) DO UPDATE SET cantidad = stock_ubicaciones.cantidad + EXCLUDED.cantidad
                                """, (prod_id, ubi_id, stock_ini))
                            conn.commit(); cursor.close(); conn.close()
                            st.success(f"✅ Producto **{nombre_prod}** registrado (SKU: {sku})"); st.balloons()
                        except Exception as e:
                            st.error(f"❌ El SKU **{sku}** ya existe." if 'productos_sku_key' in str(e) else f"❌ Error: {e}")
                    else: st.error("⚠️ SKU y Nombre son obligatorios")
            st.markdown("---")
            st.subheader("📋 Listado de Productos")
            conn = get_connection()
            prod_list = pd.read_sql("""
                SELECT p.sku, p.nombre, c.nombre as categoria, p.marca, tl.nombre as tipo_lente, ml.nombre as material, tr.nombre as tratamiento,
                       l.nombre as laboratorio, pv.nombre as proveedor, u.nombre as ubicacion,
                       p.costo_unitario_bs, p.costo_unitario_usd, p.precio_venta, i.nombre as impuesto, p.uso_venta, p.uso_compra,
                       p.stock_actual, p.stock_minimo, p.foto_url
                FROM productos p LEFT JOIN categorias c ON p.categoria_id = c.id
                LEFT JOIN tipos_lente tl ON p.tipo_lente_id = tl.id LEFT JOIN materiales_lente ml ON p.material_id = ml.id
                LEFT JOIN tratamientos tr ON p.tratamiento_id = tr.id LEFT JOIN laboratorios l ON p.laboratorio_id = l.id
                LEFT JOIN proveedores pv ON p.proveedor_id = pv.id LEFT JOIN ubicaciones u ON p.ubicacion_id = u.id
                LEFT JOIN impuestos i ON p.impuesto_id = i.id
                WHERE p.activo = TRUE ORDER BY p.nombre
            """, conn); conn.close()
            if not prod_list.empty:
                prod_list['uso_venta'] = prod_list['uso_venta'].map({True: '✅ Venta', False: '—'})
                prod_list['uso_compra'] = prod_list['uso_compra'].map({True: '✅ Compra', False: '—'})
                st.dataframe(prod_list.drop(columns=['foto_url']), use_container_width=True, height=350)
                c1, c2 = st.columns(2)
                with c1: st.metric("Total Productos", len(prod_list))
                with c2: st.metric("Stock Bajo", len(prod_list[prod_list['stock_actual'] <= prod_list['stock_minimo']]))
                con_foto = prod_list[prod_list['foto_url'].notna()]
                if not con_foto.empty:
                    with st.expander("️ Ver imagen de un producto"):
                        prod_img_sel = st.selectbox("Selecciona producto:", [f"{r['sku']} - {r['nombre']}" for _, r in con_foto.iterrows()], key="prod_img_sel")
                        if prod_img_sel:
                            ruta = con_foto[con_foto['sku'] == prod_img_sel.split(' - ')[0]]['foto_url'].values[0]
                            ruta_completa = os.path.join(os.path.dirname(os.path.abspath(__file__)), ruta)
                            if os.path.exists(ruta_completa): st.image(ruta_completa, caption=prod_img_sel)
                            else: st.warning("⚠️ Imagen no encontrada")
            else: st.info("📭 No hay productos registrados aún.")
        
        with tab_dist:
            st.subheader("📍 Distribuir Stock por Ubicación")
            st.info("💡 Selecciona un producto y distribuye su stock total entre los anaqueles/ubicaciones")
            conn = get_connection()
            prod_opts = pd.read_sql("""
                SELECT p.id, p.sku, p.nombre, p.stock_actual,
                       COALESCE((SELECT SUM(su.cantidad) FROM stock_ubicaciones su WHERE su.producto_id = p.id), 0) as stock_distribuido
                FROM productos p WHERE p.activo = TRUE ORDER BY p.nombre
            """, conn)
            ubi_all = pd.read_sql("SELECT id, nombre FROM ubicaciones WHERE activo = TRUE ORDER BY nombre", conn)
            conn.close()
            if prod_opts.empty:
                st.warning("📭 No hay productos registrados")
            else:
                prod_sel = st.selectbox(
                    "Producto:",
                    [f"{r['sku']} - {r['nombre']} (Total: {int(r['stock_actual'])} | Distribuido: {int(r['stock_distribuido'])})" for _, r in prod_opts.iterrows()],
                    key="dist_prod_sel"
                )
                prod_id = int(prod_opts.iloc[[f"{r['sku']} - {r['nombre']}" in prod_sel for _, r in prod_opts.iterrows()].index(True)]['id'])
                prod_row = prod_opts[prod_opts['id'] == prod_id].iloc[0]
                stock_total = int(prod_row['stock_actual'])
                stock_distribuido = int(prod_row['stock_distribuido'])
                stock_pendiente = stock_total - stock_distribuido
                
                st.markdown(f"**Stock Total:** {stock_total} | **Distribuido:** {stock_distribuido} | **Pendiente de distribuir:** {stock_pendiente}")
                
                conn = get_connection()
                dist_actual = pd.read_sql("""
                    SELECT u.nombre as ubicacion, su.cantidad, su.fecha_actualizacion
                    FROM stock_ubicaciones su JOIN ubicaciones u ON su.ubicacion_id = u.id
                    WHERE su.producto_id = %s ORDER BY u.nombre
                """, conn, params=(prod_id,))
                conn.close()
                if not dist_actual.empty:
                    st.markdown("#### Distribución actual:")
                    st.dataframe(dist_actual, use_container_width=True, height=150)
                
                st.markdown("#### ➕ Agregar/Modificar distribución:")
                with st.form("form_distribuir"):
                    ubi_sel = st.selectbox("Ubicación:", ubi_all['nombre'].tolist(), key="dist_ubi_sel")
                    cantidad = st.number_input("Cantidad a asignar:", min_value=0, step=1, value=0, key="dist_cant")
                    if st.form_submit_button("💾 Actualizar Distribución", type="primary", use_container_width=True):
                        if cantidad > 0:
                            ubi_id = int(ubi_all[ubi_all['nombre'] == ubi_sel]['id'].values[0])
                            conn = get_connection(); cur = conn.cursor()
                            cur.execute("""
                                INSERT INTO stock_ubicaciones (producto_id, ubicacion_id, cantidad)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (producto_id, ubicacion_id) DO UPDATE SET cantidad = EXCLUDED.cantidad, fecha_actualizacion = CURRENT_TIMESTAMP
                            """, (prod_id, ubi_id, cantidad))
                            conn.commit(); cur.close(); conn.close()
                            st.success(f"✅ {cantidad} unidades asignadas a **{ubi_sel}**"); st.rerun()
                        else: st.warning("⚠️ Ingresa una cantidad mayor a 0")
                
                st.markdown("#### 🗑️ Quitar distribución de una ubicación:")
                if not dist_actual.empty:
                    ubi_del = st.selectbox("Ubicación a limpiar:", dist_actual['ubicacion'].tolist(), key="dist_ubi_del")
                    if st.button("🗑️ Quitar de esta ubicación", use_container_width=True, key="dist_quitar"):
                        ubi_id = int(ubi_all[ubi_all['nombre'] == ubi_del]['id'].values[0])
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute("DELETE FROM stock_ubicaciones WHERE producto_id = %s AND ubicacion_id = %s", (prod_id, ubi_id))
                        conn.commit(); cur.close(); conn.close()
                        st.success(f"✅ Distribución de **{ubi_del}** eliminada"); st.rerun()
        
        with tab_cons:
            st.subheader("🔍 Consulta de Stock por Ubicación")
            conn = get_connection()
            ubi_cons = pd.read_sql("SELECT id, nombre FROM ubicaciones WHERE activo = TRUE ORDER BY nombre", conn)
            conn.close()
            if ubi_cons.empty:
                st.warning(" No hay ubicaciones registradas")
            else:
                ubi_sel_cons = st.selectbox("Selecciona la ubicación a consultar:", ubi_cons['nombre'].tolist(), key="cons_ubi_sel")
                ubi_id_cons = int(ubi_cons[ubi_cons['nombre'] == ubi_sel_cons]['id'].values[0])
                conn = get_connection()
                stock_ubi = pd.read_sql("""
                    SELECT p.sku, p.nombre, p.marca, p.modelo, su.cantidad as stock_en_ubicacion, p.stock_minimo
                    FROM stock_ubicaciones su
                    JOIN productos p ON su.producto_id = p.id
                    WHERE su.ubicacion_id = %s AND p.activo = TRUE
                    ORDER BY p.nombre
                """, conn, params=(ubi_id_cons,))
                conn.close()
                if stock_ubi.empty:
                    st.info(f"📭 No hay stock en **{ubi_sel_cons}**")
                else:
                    stock_ubi['alerta'] = stock_ubi.apply(lambda x: ' Bajo' if x['stock_en_ubicacion'] <= x['stock_minimo'] else ' OK', axis=1)
                    st.dataframe(stock_ubi, use_container_width=True, height=400)
                    st.markdown(f"**Total de productos en {ubi_sel_cons}:** {len(stock_ubi)}")
                    st.markdown(f"**Productos con stock bajo:** {len(stock_ubi[stock_ubi['alerta'] == '🔴 Bajo'])}")

    # ═══════════════════════════════════════════════════════
    #  COMPRAS - FACTURAS DE PROVEEDORES
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "compras":
        st.title("🛒 Factura de Proveedores")
        if 'carrito_compra' not in st.session_state: st.session_state.carrito_compra = []
        
        tab_nueva, tab_list = st.tabs([" Nueva Factura", "📋 Historial de Compras"])
        
        with tab_nueva:
            st.subheader("📄 Datos del Encabezado")
            conn = get_connection()
            prov_df = pd.read_sql("SELECT id, nombre, rif FROM proveedores WHERE activo = TRUE ORDER BY nombre", conn)
            ubi_df = pd.read_sql("SELECT id, nombre FROM ubicaciones WHERE activo = TRUE ORDER BY nombre", conn)
            imp_df = pd.read_sql("SELECT id, nombre, tasa FROM impuestos WHERE activo = TRUE ORDER BY nombre", conn)
            conn.close()
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                prov_sel = st.selectbox("Proveedor *", ["Seleccionar..."] + prov_df['nombre'].tolist(), key="comp_prov")
                num_factura = st.text_input("N° Factura", key="comp_fact")
                fecha_comp = st.date_input("Fecha", value=date.today(), key="comp_fecha")
            with c2:
                num_control = st.text_input("N° Control", key="comp_ctrl")
                moneda = st.selectbox("Moneda", ["USD", "Bs"], index=0, key="comp_mon")
                cond_pago = st.text_input("Cond. de Pago", key="comp_cond")
            with c3:
                st.markdown("**Totales**")
                st.markdown(f"**Subtotal:** ${sum(l['total'] for l in st.session_state.carrito_compra):.2f}")
                desc_global = st.number_input("Descuento global $", min_value=0.0, step=0.01, value=0.0, key="comp_desc")
                recargo = st.number_input("Recargo $", min_value=0.0, step=0.01, value=0.0, key="comp_rec")
            with c4:
                imp_sel = st.selectbox("Impuesto", ["Seleccionar..."] + imp_df['nombre'].tolist(), key="comp_imp")
                tasa_imp = float(imp_df[imp_df['nombre'] == imp_sel]['tasa'].values[0]) if imp_sel != "Seleccionar..." and not imp_df.empty else 0
                st.info(f"Tasa: {tasa_imp}%")
            
            st.markdown("---")
            st.subheader("📦 Items de la Factura")
            c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 1, 1.5, 1, 1.5])
            with c1:
                busc_prod = st.text_input("Buscar producto:", key="comp_busc")
                conn = get_connection()
                if busc_prod:
                    prods = pd.read_sql("SELECT id, sku, nombre, stock_actual FROM productos WHERE activo=TRUE AND (nombre ILIKE %s OR sku ILIKE %s) ORDER BY nombre", conn, params=(f'%{busc_prod}%', f'%{busc_prod}%'))
                else:
                    prods = pd.read_sql("SELECT id, sku, nombre, stock_actual FROM productos WHERE activo=TRUE ORDER BY nombre LIMIT 30", conn)
                conn.close()
                if prods.empty:
                    prod_sel = None
                else:
                    prod_sel = st.selectbox("Producto:", [f"{r['sku']} - {r['nombre']} (Stock: {int(r['stock_actual'])})" for _, r in prods.iterrows()], key="comp_prod")
            with c2: unidad = st.text_input("Unidad", value="UND", key="comp_uni")
            with c3: cant_comp = st.number_input("Cantidad", min_value=1, step=1, value=1, key="comp_cant")
            with c4: costo_u = st.number_input("Costo Unit.", min_value=0.0, step=0.01, value=0.0, key="comp_costo")
            with c5: desc_pct = st.number_input("Desc %", min_value=0.0, max_value=100.0, step=0.5, value=0.0, key="comp_descp")
            with c6:
                ubi_sel_item = st.selectbox("Ubicación", ["Seleccionar..."] + ubi_df['nombre'].tolist(), key="comp_ubi")
                if st.button(" Añadir", use_container_width=True, key="comp_add"):
                    if prod_sel and cant_comp > 0 and costo_u > 0:
                        prod_id = int(prods.iloc[[f"{r['sku']} - {r['nombre']}" in prod_sel for _, r in prods.iterrows()].index(True)]['id'])
                        prod_nom = prods.iloc[[f"{r['sku']} - {r['nombre']}" in prod_sel for _, r in prods.iterrows()].index(True)]['nombre'].values[0]
                        total_linea = round(cant_comp * costo_u * (1 - desc_pct/100.0), 2)
                        st.session_state.carrito_compra.append({
                            'producto_id': prod_id, 'descripcion': prod_nom, 'unidad': unidad,
                            'cantidad': int(cant_comp), 'costo_unitario': float(costo_u),
                            'descuento_pct': float(desc_pct), 'total': total_linea,
                            'ubicacion': ubi_sel_item if ubi_sel_item != "Seleccionar..." else None
                        })
                        st.rerun()
                    else: st.warning("⚠️ Selecciona producto, cantidad y costo")
            
            carrito = st.session_state.carrito_compra
            if carrito:
                dfc = pd.DataFrame(carrito)
                st.dataframe(dfc[['descripcion', 'unidad', 'cantidad', 'costo_unitario', 'descuento_pct', 'total', 'ubicacion']]
                             .rename(columns={'descripcion': 'Descripción', 'unidad': 'Unidad', 'cantidad': 'Cant.',
                                              'costo_unitario': 'Costo Unit.', 'descuento_pct': 'Desc%', 'total': 'Total', 'ubicacion': 'Ubicación'}),
                             use_container_width=True, height=200)
                if st.button("️ Limpiar carrito", use_container_width=True, key="comp_clear"):
                    st.session_state.carrito_compra = []; st.rerun()
            
            st.markdown("---")
            subtotal = sum(l['total'] for l in carrito)
            subtotal_net = subtotal - desc_global + recargo
            monto_imp = round(subtotal_net * tasa_imp / 100.0, 2)
            total_final = round(subtotal_net + monto_imp, 2)
            
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: st.markdown(f"**Subtotal**\n### ${subtotal:.2f}")
            with c2: st.markdown(f"**Afecto**\n### ${subtotal_net:.2f}")
            with c3: st.markdown(f"**Impuesto ({tasa_imp}%)**\n### ${monto_imp:.2f}")
            with c4: st.markdown(f"**Exento**\n### $0.00")
            with c5: st.markdown(f"**TOTAL**\n### ${total_final:.2f}")
            
            comentario = st.text_area("Comentario", key="comp_coment")
            
            if st.button(" Guardar Factura", type="primary", use_container_width=True, key="comp_guardar"):
                if prov_sel == "Seleccionar..." or not carrito:
                    st.error("⚠️ Selecciona proveedor y añade al menos un item")
                else:
                    try:
                        prov_id = int(prov_df[prov_df['nombre'] == prov_sel]['id'].values[0])
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO compras (proveedor_id, numero_factura, numero_control, fecha_compra, moneda, condicion_pago,
                            subtotal, descuento, recargo, impuesto, total, afecto, exento, base_imponible, comentario)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                        """, (prov_id, num_factura, num_control, fecha_comp, moneda, cond_pago,
                              subtotal, desc_global, recargo, monto_imp, total_final, subtotal_net, 0, subtotal_net, comentario))
                        comp_id = cur.fetchone()[0]
                        for item in carrito:
                            ubi_id = int(ubi_df[ubi_df['nombre'] == item['ubicacion']]['id'].values[0]) if item['ubicacion'] else None
                            cur.execute("""
                                INSERT INTO compras_detalles (compra_id, producto_id, descripcion, unidad, cantidad, costo_unitario, descuento_pct, total, ubicacion_id)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """, (comp_id, item['producto_id'], item['descripcion'], item['unidad'], item['cantidad'],
                                  item['costo_unitario'], item['descuento_pct'], item['total'], ubi_id))
                            cur.execute("UPDATE productos SET stock_actual = stock_actual + %s WHERE id = %s", (item['cantidad'], item['producto_id']))
                            if ubi_id:
                                cur.execute("""
                                    INSERT INTO stock_ubicaciones (producto_id, ubicacion_id, cantidad)
                                    VALUES (%s,%s,%s)
                                    ON CONFLICT (producto_id, ubicacion_id) DO UPDATE SET cantidad = stock_ubicaciones.cantidad + EXCLUDED.cantidad
                                """, (item['producto_id'], ubi_id, item['cantidad']))
                        conn.commit(); cur.close(); conn.close()
                        st.session_state.carrito_compra = []
                        st.success(f"✅ Factura **{num_factura or comp_id}** registrada por **${total_final:.2f}** (inventario actualizado)")
                        st.balloons(); st.rerun()
                    except Exception as e: st.error(f"❌ Error: {e}")
        
        with tab_list:
            st.subheader("📋 Historial de Compras")
            conn = get_connection()
            comp_list = pd.read_sql("""
                SELECT c.id, c.numero_factura, c.numero_control, c.fecha_compra, p.nombre as proveedor,
                       c.subtotal, c.descuento, c.impuesto, c.total, c.estado
                FROM compras c JOIN proveedores p ON c.proveedor_id = p.id
                ORDER BY c.id DESC
            """, conn); conn.close()
            if not comp_list.empty:
                comp_list['fecha_compra'] = pd.to_datetime(comp_list['fecha_compra']).dt.strftime('%d/%m/%Y')
                st.dataframe(comp_list, use_container_width=True, height=400)
                st.markdown(f"**Total de facturas:** {len(comp_list)}")
            else: st.info("📭 No hay compras registradas")

    # ═══════════════════════════════════════════════════════
    #  PROVEEDORES
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "proveedores":
        st.title(" Gestión de Proveedores")
        with st.form("form_nuevo_proveedor"):
            c1, c2 = st.columns(2)
            with c1:
                prov_nombre = st.text_input("Nombre / Razón Social *", key="prov_nom"); prov_rif = st.text_input("RIF (J-12345678-9)", key="prov_rif")
                prov_tipo = st.selectbox("Tipo", ["Distribuidor", "Laboratorio", "Fabricante", "Otro"], key="prov_tipo"); prov_contacto = st.text_input("Contacto", key="prov_cont")
            with c2:
                prov_tel = st.text_input("Teléfono", key="prov_tel"); prov_email = st.text_input("Email", key="prov_email"); prov_dir = st.text_area("Dirección", key="prov_dir")
            if st.form_submit_button("💾 Guardar Proveedor", type="primary", use_container_width=True):
                if prov_nombre:
                    try:
                        conn = get_connection(); cursor = conn.cursor()
                        cursor.execute("INSERT INTO proveedores (nombre, rif, tipo, contacto, telefono, email, direccion) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                                       (prov_nombre, prov_rif, prov_tipo, prov_contacto, prov_tel, prov_email, prov_dir))
                        conn.commit(); cursor.close(); conn.close()
                        st.success(f"✅ Proveedor **{prov_nombre}** registrado")
                    except Exception as e: st.error(f"❌ Error: {e}")
                else: st.error("⚠️ El nombre es obligatorio")
        st.markdown("---")
        conn = get_connection()
        prov_list = pd.read_sql("SELECT id, nombre, rif, tipo, contacto, telefono, email FROM proveedores WHERE activo = TRUE ORDER BY nombre", conn); conn.close()
        if not prov_list.empty:
            st.dataframe(prov_list, use_container_width=True, height=250)
            prov_del = st.selectbox("Eliminar proveedor:", [f"{r['nombre']} (RIF: {r['rif'] or 'N/A'})" for _, r in prov_list.iterrows()], key="prov_del_sel")
            if st.button("🗑️ Eliminar", key="btn_prov_del"):
                prov_id = int(prov_list[prov_list['nombre'] == prov_del.split(' (RIF:')[0].strip()]['id'].values[0])
                conn = get_connection(); cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM productos WHERE proveedor_id = %s", (prov_id,)); usados = cursor.fetchone()[0]
                if usados > 0: st.error(f"❌ No se puede eliminar: {usados} producto(s) asociado(s)")
                else:
                    cursor.execute("UPDATE proveedores SET activo = FALSE WHERE id = %s", (prov_id,)); conn.commit(); st.success("✅ Proveedor eliminado")
                cursor.close(); conn.close()
        else: st.info("📭 No hay proveedores registrados.")

    # ═══════════════════════════════════════════════════════
    # ️ CATÁLOGOS
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "catalogos":
        st.title("⚙️ Catálogos del Sistema")
        st.info("💡 Aquí gestionas los valores de todos los combobox del sistema")
        CATALOGOS = {
            " Estados de Pedido": "estados_pedido", " Tipos de Lente": "tipos_lente", "🧪 Materiales de Lente": "materiales_lente",
            "✨ Tratamientos": "tratamientos", "🏭 Laboratorios": "laboratorios", "📍 Ubicaciones": "ubicaciones", "💵 Impuestos": "impuestos",
        }
        USO_EN_PRODUCTOS = {
            "tipos_lente": "tipo_lente_id", "materiales_lente": "material_id", "tratamientos": "tratamiento_id",
            "laboratorios": "laboratorio_id", "ubicaciones": "ubicacion_id", "impuestos": "impuesto_id",
        }
        cat_sel_mgmt = st.selectbox("Catálogo a gestionar:", list(CATALOGOS.keys()), key="cat_mgmt_sel")
        tabla = CATALOGOS[cat_sel_mgmt]
        st.markdown(f"#### ➕ Agregar valor a: **{cat_sel_mgmt}**")
        c1, c2, c3 = st.columns([3, 3, 1])
        with c1: nuevo_valor = st.text_input("Nuevo valor:", key=f"cat_new_{tabla}")
        with c2:
            extra_contacto = ""; extra_telefono = ""; extra_tasa = 0.0
            if tabla == "laboratorios":
                extra_contacto = st.text_input("Contacto:", key="cat_lab_cont"); extra_telefono = st.text_input("Teléfono:", key="cat_lab_tel")
            if tabla == "impuestos":
                extra_tasa = st.number_input("Tasa (%):", min_value=0.0, step=0.5, key="cat_imp_tasa")
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Agregar", use_container_width=True, key=f"cat_add_{tabla}"):
                if nuevo_valor:
                    try:
                        conn = get_connection(); cursor = conn.cursor()
                        if tabla == "laboratorios":
                            cursor.execute("INSERT INTO laboratorios (nombre, contacto, telefono) VALUES (%s,%s,%s) ON CONFLICT (nombre) DO NOTHING", (nuevo_valor, extra_contacto, extra_telefono))
                        elif tabla == "impuestos":
                            cursor.execute("INSERT INTO impuestos (nombre, tasa) VALUES (%s,%s) ON CONFLICT (nombre) DO NOTHING", (nuevo_valor, extra_tasa))
                        else:
                            cursor.execute(f"INSERT INTO {tabla} (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING", (nuevo_valor,))
                        conn.commit()
                        if cursor.rowcount == 0: st.warning(f"⚠️ '{nuevo_valor}' ya existe")
                        else: st.success(f"✅ '{nuevo_valor}' agregado")
                        cursor.close(); conn.close(); st.rerun()
                    except Exception as e: st.error(f" Error: {e}")
                else: st.warning("⚠️ Escribe un valor")
        st.markdown(f"####  Valores actuales de: **{cat_sel_mgmt}**")
        conn = get_connection()
        if tabla == "impuestos":
            cat_list = pd.read_sql(f"SELECT id, nombre, tasa FROM {tabla} WHERE activo = TRUE ORDER BY nombre", conn)
        else:
            cat_list = pd.read_sql(f"SELECT id, nombre FROM {tabla} WHERE activo = TRUE ORDER BY nombre", conn)
        conn.close()
        if not cat_list.empty:
            st.dataframe(cat_list, use_container_width=True, height=200)
            c1, c2 = st.columns([3, 1])
            with c1: valor_del = st.selectbox("Valor a eliminar:", cat_list['nombre'].tolist(), key=f"cat_del_sel_{tabla}")
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️ Eliminar", use_container_width=True, key=f"cat_del_{tabla}"):
                    val_id = int(cat_list[cat_list['nombre'] == valor_del]['id'].values[0])
                    conn = get_connection(); cursor = conn.cursor()
                    if tabla in USO_EN_PRODUCTOS:
                        cursor.execute(f"SELECT COUNT(*) FROM productos WHERE {USO_EN_PRODUCTOS[tabla]} = %s", (val_id,)); usados = cursor.fetchone()[0]
                        if usados > 0:
                            st.error(f"❌ No se puede eliminar: {usados} producto(s) lo usan"); cursor.close(); conn.close(); st.stop()
                    cursor.execute(f"UPDATE {tabla} SET activo = FALSE WHERE id = %s", (val_id,))
                    conn.commit(); cursor.close(); conn.close()
                    st.success(f"✅ '{valor_del}' eliminado"); st.rerun()
        else:
            st.info("📭 Este catálogo está vacío. Agrega el primer valor arriba.")

    # ═══════════════════════════════════════════════════════
    # OTRAS PÁGINAS
    # ═══════════════════════════════════════════════════════
    elif st.session_state.page == "ventas":
        st.title("💰 Ventas")
        st.info(" Módulo en desarrollo... Próximamente disponible")

    elif st.session_state.page == "cartera":
        st.title("📊 Cartera de Clientes")
        st.info("🚧 Módulo en desarrollo... Próximamente disponible")
