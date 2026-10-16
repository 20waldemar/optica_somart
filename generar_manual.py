# -*- coding: utf-8 -*-
"""Genera el Manual de Usuario en PDF. Uso: python generar_manual.py"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

NOMBRE_OPTICA = "ÓPTICA SOTMAR"          # ← edita con el nombre real
SISTEMA = "ÓpticaVision Pro"
VERSION = "1.0"
FECHA = "Octubre 2026"
SOPORTE = "Soporte técnico: Ing. Waldemar - 0412-154-125"   # ← edita
CAPTURAS = "capturas"

est = getSampleStyleSheet()
tit = ParagraphStyle('tit', parent=est['Title'], fontSize=26, textColor=colors.HexColor('#1F6FB2'), alignment=TA_CENTER)
sub = ParagraphStyle('sub', parent=est['Normal'], fontSize=12, alignment=TA_CENTER, textColor=colors.grey)
h1 = ParagraphStyle('h1', parent=est['Heading1'], fontSize=15, textColor=colors.HexColor('#1F6FB2'), spaceBefore=10, spaceAfter=6)
cuerpo = ParagraphStyle('cuerpo', parent=est['Normal'], fontSize=10, leading=15, spaceAfter=4)
paso = ParagraphStyle('paso', parent=cuerpo, leftIndent=16, spaceAfter=3)
nota = ParagraphStyle('nota', parent=cuerpo, textColor=colors.HexColor('#B00020'), fontSize=9)

doc = SimpleDocTemplate("Manual_Usuario_OpticaVision.pdf", pagesize=letter,
                        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
                        title=f"Manual de Usuario {SISTEMA}", author=NOMBRE_OPTICA)
e = []

def cap(nombre):
    ruta = os.path.join(CAPTURAS, nombre)
    if os.path.exists(ruta):
        img = Image(ruta)
        img._restrictSize(16*cm, 9.5*cm)
        e.append(Spacer(1, 0.2*cm)); e.append(img); e.append(Spacer(1, 0.3*cm))

def seccion(titulo, intro, pasos, notas=None, captura=None):
    e.append(Paragraph(titulo, h1))
    if intro: e.append(Paragraph(intro, cuerpo))
    for p in pasos: e.append(Paragraph(p, paso))
    if notas:
        for n in notas: e.append(Paragraph("⚠ " + n, nota))
    if captura: cap(captura)

# ── PORTADA ──
e.append(Spacer(1, 4*cm))
e.append(Paragraph(NOMBRE_OPTICA, tit))
e.append(Spacer(1, 0.5*cm))
e.append(Paragraph(f"Manual de Usuario del Sistema<br/><b>{SISTEMA} v{VERSION}</b>", sub))
e.append(Spacer(1, 1*cm))
e.append(Paragraph(FECHA, sub))
e.append(Spacer(1, 6*cm))
e.append(Paragraph("Uso interno – Documento de apoyo para la operación diaria", sub))
e.append(Paragraph(SOPORTE, sub))
e.append(PageBreak() if False else Spacer(1, 0))
from reportlab.platypus import PageBreak
e.append(PageBreak())

# ── CONTENIDO ──
e.append(Paragraph("Contenido", h1))
toc = [["1.", "Entrar al sistema (Login)"], ["2.", "Pantalla principal y menú"], ["3.", "Pacientes"],
       ["4.", "Consultas y graduación"], ["5.", "Orden en PDF"], ["6.", "Pedidos, Ventas y Cobros"],
       ["7.", "Inventario"], ["8.", "Cambiar contraseña"], ["9.", "Buenas prácticas y respaldo"]]
t = Table(toc, colWidths=[1*cm, 15*cm])
t.setStyle(TableStyle([('FONTSIZE', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
e.append(t); e.append(PageBreak())

seccion("1. Entrar al sistema (Login)",
        "Para iniciar, haga doble click en el ícono <b>ÓpticaVision</b> del escritorio. Espere unos segundos a que se abra el navegador.",
        ["1. Escriba su usuario: <b>admin</b>",
         "2. Escriba su contraseña (la inicial es <b>admin123</b>, cámbiela según la sección 8).",
         "3. Presione el botón <b>🔐 Ingresar</b>."],
        ["Si el navegador no se abre solo, escriba en la barra de direcciones: http://localhost:8501",
         "Nunca cierre la ventana negra (consola) mientras usa el sistema: es el motor de la aplicación."],
        "01_login.png")

seccion("2. Pantalla principal y menú",
        "A la izquierda encontrará el menú con todos los módulos: Dashboard, Pacientes, Exámenes, Consultas, Pedidos, Inventario, Proveedores, Catálogos y Cambiar Contraseña.",
        ["1. El <b>Dashboard</b> muestra los contadores de pacientes, exámenes, consultas y productos.",
         "2. Para cambiar de módulo, haga click en el botón correspondiente del menú.",
         "3. Con <b>🚪 Cerrar Sesión</b> sale del sistema de forma segura."],
        None, "02_dashboard.png")

seccion("3. Pacientes",
        "Registro y control de la ficha del paciente (adultos y menores con representante).",
        ["1. Entre a <b>👤 Pacientes → ➕ Nuevo Paciente</b>.",
         "2. Si conoce la cédula, use la <b>Búsqueda Rápida</b>: si ya existe lo trae a pantalla para editarlo; si no, continúe el registro.",
         "3. Complete nombre, apellidos, cédula (única), fecha de nacimiento (la edad se calcula sola), sexo, teléfono y dirección.",
         "4. Para menores, marque la casilla y registre o seleccione el representante.",
         "5. Presione <b>💾 Guardar Paciente</b>.",
         "6. En <b>📋 Listado</b> puede exportar a CSV y eliminar pacientes sin historial.",
         "7. En <b>🔍 Buscar</b>, haga click sobre una fila para Ver o Editar el paciente."],
        ["La cédula no se puede repetir: el sistema avisa si ya existe.",
         "No se pueden eliminar pacientes con exámenes, pedidos o pagos."],
        "03_pacientes.png")

seccion("4. Consultas y graduación",
        "Cada atención al paciente queda registrada como una consulta con su historial.",
        ["1. Entre a <b>🩺 Consultas</b> y seleccione el paciente.",
         "2. Presione <b>➕ Nueva Consulta</b> o abra una fecha del historial (panel izquierdo).",
         "3. Pestaña <b>Datos de Consulta</b>: motivo, síntomas y diagnóstico.",
         "4. Pestaña <b>Antecedentes y Examen Ocular</b>: antecedentes, alergias, cirugías y tablas de agudeza visual (SIN RX / RX ANT / PH), queratometría y refracciones.",
         "5. Pestaña <b>Graduación y Envío a Lab</b>: Rx Final (OD/OI), tipo de lente, material, tratamiento, laboratorio y urgencia del pedido.",
         "6. Presione <b>💾 Guardar Consulta</b> y luego <b>🔬 Guardar Graduación y Lab.</b>",
         "7. Con <b>📤 Envío a Pedido</b> el pedido pasa al laboratorio (estado 'Enviado a Lab.')."],
        ["Guarde siempre la consulta ANTES de guardar la graduación."],
        "04_consultas.png")

seccion("5. Orden en PDF",
        "La orden/receta se genera lista para imprimir o enviar por WhatsApp/correo.",
        ["1. Con la consulta guardada y graduación cargada, presione <b>📄 Generar PDF</b>.",
         "2. Aparecerá el botón <b>⬇️ Descargar PDF</b>: guárdelo o imprímalo.",
         "3. También puede reimprimir órdenes anteriores en la pestaña <b>📄 Generar PDF</b> de Consultas, eligiendo la orden de la lista.",
         "4. El PDF incluye: encabezado de la óptica, N° de orden, fecha y hora, datos del paciente, tabla Rx Final, lente/materiales y datos del laboratorio con firmas."],
        None, "06_pdf.png")

seccion("6. Pedidos, Ventas y Cobros",
        "Módulo <b>🧾 Pedidos</b>: control total del ciclo pedido → venta → cobro.",
        ["1. Pestaña <b>📦 Pedidos y Ventas</b>: filtros por fecha, estado, venta y pendiente de cobro. Seleccione un pedido para cambiar su estado, registrar el total de la venta o eliminarlo.",
         "2. Pestaña <b>💰 Registrar Venta</b>: elija el pedido, busque productos (muestra existencias), indique precio, cantidad y descuento %, presione <b>🛒 Añadir</b>. El sistema calcula Sub Total, IVA y Total. Puede dejar un abono inicial.",
         "3. Al guardar, el inventario se descuenta automáticamente.",
         "4. Pestaña <b>💵 Cobros / Abonos</b>: seleccione la venta, vea el saldo pendiente, registre abonos con concepto y método, o anule cobros equivocados (el saldo se recalcula).",
         "5. Puede anular una venta completa: repone el stock y elimina sus abonos."],
        ["Un pedido sin venta registrada no aparece en Cobros.",
         "Revise el 'Pendiente' antes de cerrar el día."],
        "07_pedidos.png")

seccion("7. Inventario",
        "Master de productos con foto, costo en Bs y US$, impuesto y ubicación.",
        ["1. Entre a <b>📦 Inventario</b> y complete SKU, nombre, categoría, tipo de lente, material, tratamiento, laboratorio, proveedor y ubicación.",
         "2. Suba la foto del producto (vista previa inmediata).",
         "3. Indique precio de venta, stock inicial y stock mínimo, uso (venta/compra), costos e impuesto.",
         "4. El listado muestra alerta de <b>Stock Bajo</b> cuando un producto llega a su mínimo."],
        None, "10_inventario.png")

seccion("8. Cambiar contraseña",
        "Por seguridad, cambie la contraseña inicial del sistema.",
        ["1. En el menú lateral presione <b>🔑 Cambiar Contraseña</b>.",
         "2. Escriba su contraseña actual, la nueva (mínimo 6 caracteres) y confírmela.",
         "3. Presione <b>💾 Actualizar Contraseña</b>. Úsela desde el siguiente inicio de sesión."],
        ["Anote su nueva contraseña en un lugar seguro. Si la olvida, contacte al soporte."],
        "11_contrasena.png")

seccion("9. Buenas prácticas y respaldo",
        "Recomendaciones para proteger la información del negocio.",
        ["1. No apague la laptop ni cierre la ventana negra durante un guardado.",
         "2. Una vez por semana genere un respaldo: abra pgAdmin → click derecho en <b>optica_db</b> → <b>Backup</b> → formato <b>Plain</b> → guarde el archivo en un USB.",
         "3. Mantenga el USB del instalador y los respaldos fuera de la oficina.",
         "4. Cualquier ajuste de catálogos (estados, laboratorios, impuestos) se hace en <b>⚙️ Catálogos</b>, sin llamar al soporte."],
        [SOPORTE])

doc.build(e)
print("✅ Manual generado: Manual_Usuario_OpticaVision.pdf")