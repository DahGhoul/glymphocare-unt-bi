# Guía Paso a Paso: Despliegue 100% Gratis en AWS (Sin Experiencia Previa)

> **Nota importante para el curso (Asesoría 13/11/2026):** El docente exige usar **al menos una herramienta de la plataforma asignada (AWS)** y demostrar los KPIs/Data Mart contra ella. Con solo completar la **Parte A + Parte B (Amazon RDS PostgreSQL Free Tier)** en ~10 minutos ya cumples al 100% el requisito AWS y puedes presentar tu app conectada en vivo a la nube desde tu laptop. La **Parte C (EC2)** es opcional para publicar la URL pública.

---

## Parte A — Cómo conseguir cuenta AWS gratis y blindarla contra cobros ($0.00)

1. **Opción 1 (Si algún compañero tiene tarjeta débito/crédito Visa/Mastercard):**
   - Entra a https://aws.amazon.com/es/free/ y crea una cuenta **AWS Free Tier** (te retiene $1 USD temporal para validar y lo devuelve).
   - Apenas entres a la consola busca **AWS Budgets** → *Create a budget* → *Zero spend budget* (alerta a tu correo si llega a $0.01). Con eso nunca tendrás cobros sorpresa.
2. **Opción 2 (Sin tarjeta — AWS Academy / Crédito estudiantil):**
   - Si en la UNT tienen **AWS Academy Learner Lab**, inicia tu laboratorio (*Start Lab*) y crea el RDS ahí.

---

## Parte B — Subir la Base Transaccional + Data Mart a Amazon RDS (10 minutos)

1. En la consola AWS busca **RDS** → **Create database**:
   - Creation method: **Standard create**
   - Engine: **PostgreSQL** (versión 16.x)
   - Template: **Free tier** *(muy importante para que sea $0)*
   - DB instance identifier: `glymphocare-db`
   - Master username: `postgres`
   - Master password: escribe una contraseña segura (ej. `<TU_CONTRASENA_SEGURA>`) y anótala
   - Public access: **Yes** *(necesario para conectarte desde tu laptop y DBeaver)*
   - Initial database name (en *Additional configuration*): `glymphocare`
   - Clic en **Create database** y espera ~4 minutos hasta que diga *Available*.
2. Haz clic en `glymphocare-db`, copia el **Endpoint** (ej. `glymphocare-db.xxxx.us-east-1.rds.amazonaws.com`).
3. En la sección *Connectivity & security* → clic en el **VPC security group** → *Edit inbound rules* → **Add rule**:
   - Type: `PostgreSQL` (puerto `5432`)
   - Source: `My IP` (o `0.0.0.0/0` solo durante la presentación) → **Save rules**.
4. Abre PowerShell en la carpeta `glymphocare\deploy\aws` y ejecuta nuestro script automático:
   ```powershell
   .\migrate_to_rds.ps1 -RdsHost "TU-ENDPOINT-RDS" -RdsPassword "TU-CLAVE"
   ```
   Este script crea los esquemas `glympho_oltp` y `glympho_dw`, carga los 90 estudiantes, corre el ETL y deja tu app local conectada directamente a **Amazon RDS**.

---

## Parte C — (Opcional) Publicar la Web Pública en Amazon EC2 (`t3.micro` Free Tier)

1. En consola AWS busca **EC2** → **Launch instance**:
   - Name: `glymphocare-web`, OS: **Ubuntu 24.04 LTS**, Instance type: **`t3.micro`** (Free tier).
   - Key pair: crea y descarga `glymphocare.pem`.
   - Firewall: marca **Allow HTTP** (puerto 80) y **Allow HTTPS** (puerto 443) y SSH (22).
2. Conéctate por SSH, instala Docker + Docker Compose, sube la carpeta `glymphocare/` (con tu `.env` apuntando al RDS) y ejecuta:
   ```bash
   cd glymphocare/deploy/aws
   docker compose -f docker-compose.prod.yml up -d --build
   ```
   ¡Listo! Tu app quedará accesible desde cualquier celular o navegador usando la IP pública de EC2.

---

## Parte D — Cómo activar Google Gemini API Gratis en 2 minutos (RF-10)

Aunque GlymphoCare ya genera interpretaciones clínicas estructuradas sin conexión externa, activar **Gemini Live** toma 2 minutos y es gratis:
1. Entra con tu Gmail a https://aistudio.google.com/apikey
2. Haz clic en **Create API key** y cópiala (`AIza...`).
3. Entra a GlymphoCare como **Admin** (`admin@glymphocare.edu.pe` / `Glympho2026!`) → pestaña **Administración y ETL** → pega la clave en *Configuración IA Generativa* → **Guardar clave**.
4. Ve a **Perfil e Interpretación IA** → pulsa **Generar interpretación IA** y verás el sello `Google Gemini (gemini-2.0-flash)`.
