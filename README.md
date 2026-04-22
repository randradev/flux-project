# FLUX - Banca Digital Conversacional

![FLUX Banner](https://img.shields.io/badge/FLUX-Digital_Banking-blue?style=for-the-badge&logo=google-gemini)

**FLUX** es una plataforma de banca digital de próxima generación que transforma la solicitud de productos financieros tradicionales en una experiencia fluida, asistida por IA y basada en estados. Utiliza orquestación avanzada para guiar al usuario a través de flujos complejos sin la fricción de los formularios estáticos.

## 🚀 Propósito del Proyecto

FLUX utiliza **grafos de estado** para orquestar la lógica de negocio, permitiendo que un asistente virtual guíe al usuario desde la intención inicial hasta la formalización legal. El sistema se aleja del concepto de "chat genérico" para convertirse en un motor de estados persistente y determinista.

### Flujos Soportados (MVP)
1.  **Crédito de Consumo:** Evaluación de riesgo mediante scoring y capacidad de pago.
2.  **Cuenta Corriente:** Apertura segmentada (Start, Medium, Advance).
3.  **DAP (Depósito a Plazo):** Simulación de inversiones dinámica.

---

## 🛠️ Tecnologías Utilizadas

### Frontend
-   **React 19:** Interfaz reactiva y moderna.
-   **Vite:** Herramienta de construcción ultra rápida.
-   **Vanilla CSS:** Diseño premium a medida con variables dinámicas y micro-animaciones.

### Backend
-   **FastAPI:** Framework de alto rendimiento para la API.
-   **LangGraph & LangChain:** Orquestación de grafos de estado y flujos conversacionales.
-   **Google Vertex AI (Gemini 3 Flash):** Motor de inteligencia artificial para extracción de entidades y ruteo.
-   **Supabase:** Base de datos relacional y persistencia de checkpoints.
-   **Pydantic:** Validación de datos y contratos estrictos.
-   **ReportLab:** Generación dinámica de contratos en PDF con sellado SHA-256.

---

## 📋 Requisitos

Antes de comenzar, asegúrate de tener instalado:
-   [Python 3.10+](https://www.python.org/)
-   [Node.js (LTS)](https://nodejs.org/)
-   Cuenta en [Google Cloud Platform](https://console.cloud.google.com/) con Vertex AI habilitado.
-   Proyecto en [Supabase](https://supabase.com/).

---

## 🔧 Instalación y Uso

### 1. Clonar el Repositorio
```bash
git clone <url-del-repositorio>
cd flux-project
```

### 2. Configuración del Backend
Navega a la carpeta del backend y configura el entorno:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # En Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```
Crea un archivo `.env` basado en la documentación de `backend/docs/documentacion-backend/setup-backend.md` con tus credenciales de Google Cloud y Supabase.

Ejecuta el servidor:
```bash
python main.py
```

### 3. Configuración del Frontend
Navega a la carpeta del frontend e instala las dependencias:
```bash
cd ../frontend
npm install
npm run dev
```
La aplicación estará disponible en `http://localhost:5173`.

---

## 🏛️ Arquitectura

El proyecto sigue una arquitectura de **Orquestación de Estados**:
-   **Router de Intenciones:** Clasifica la necesidad del usuario.
-   **Extracción de Entidades:** Convierte lenguaje natural en datos estructurados (JSONB).
-   **Persistencia (Checkpoints):** Permite retomar conversaciones en cualquier punto.
-   **Motores de Cálculo:** Lógica pura para riesgo, amortización y segmentación.

---

## 🤝 Cómo Contribuir

¡Las contribuciones son bienvenidas! Para colaborar:
1.  Haz un **Fork** del proyecto.
2.  Crea una nueva rama (`git checkout -b feature/NuevaFuncionalidad`).
3.  Realiza tus cambios y haz **Commit** (`git commit -m 'Add some feature'`).
4.  Sube tus cambios (`git push origin feature/NuevaFuncionalidad`).
5.  Abre un **Pull Request**.

---

## 📄 Licencia

Este proyecto es de uso privado para el desarrollo de FLUX.
