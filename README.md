# Proyecto 1: Obtención y Limpieza de Datos

**Universidad del Valle de Guatemala**  
**Curso:** Data Science

### Integrantes del Equipo
* Humberto Alexander de la Cruz - 23735
* Daniel Oswaldo Juárez - 23709
* Nicolle Alexandra Gordillo - 22246

---

## Descripción del Proyecto
Este proyecto automatiza la extracción, diagnóstico, limpieza y validación de los datos de establecimientos educativos a nivel diversificado de Guatemala, obtenidos del portal del MINEDUC. El objetivo principal es asegurar la consistencia, reproducibilidad y calidad de los datos para futuros análisis de Data Science.

## Estructura del Repositorio
El repositorio está organizado de la siguiente manera para garantizar la reproducibilidad de todo el proceso:

```text
├── data/
│   ├── raw/                                  # Carpeta para archivos CSV temporales por departamento
│   ├── diversificado_consolidado.csv         # Datos crudos extraídos originalmente
│   ├── diversificado_limpio.csv              # Conjunto de datos final limpio y validado
│   └── registro_transformaciones.csv         # Bitácora automatizada de modificaciones
├── descarga_establecimientos.py              # Script de web scraping (Playwright/BeautifulSoup)
├── Limpieza.ipynb                            # Notebook principal con diagnóstico, limpieza e Informe de Calidad
├── README.md                                 # Documentación del proyecto
└── requirements.txt                          # Dependencias de Python necesarias
```

## Libro de Códigos
El diccionario detallado con los metadatos de las 25 variables finales (descripción, tipos de datos, dominios permitidos y tratamientos aplicados) se encuentra disponible en el siguiente enlace:

**[Libro de Códigos - Google Docs](https://docs.google.com/document/d/10dVY6qgRMmMYnBtHVmbsuWtVqGKjf4DXYl0pgU9B70s/edit?usp=sharing)**

## Ejecución y Reproducibilidad

1. **Instalar dependencias:**
	Para preparar el entorno virtual y garantizar la ejecución del proyecto, instala las librerías requeridas:

	```bash
	pip install -r requirements.txt
	```

2. **Obtención de datos (Opcional):**
	El archivo crudo ya se encuentra respaldado en `data/diversificado_consolidado.csv`. Si se desea ejecutar la extracción nuevamente desde el portal del MINEDUC, se debe ejecutar el siguiente script:

	```bash
	python descarga_establecimientos.py
	```

3. **Limpieza, Validación e Informe de Calidad:**
	Ejecutar todas las celdas del archivo `Limpieza.ipynb`.
	
	- Diagnóstico del estado inicial de los datos crudos.
	- Ejecución de las reglas de limpieza y unificación de categorías.
	- Ejecución de pruebas automáticas (`asserts`) para comprobar la integridad y tipos de datos del conjunto limpio.
	- Despliegue del **Informe de Calidad de los Datos** (Métricas de Antes y Después) generado en vivo en las últimas celdas del Notebook.