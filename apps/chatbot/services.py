"""
Chatbot Services and Analytical Inference Layer.

PENDIENTE DE INTEGRACIÓN:
Este módulo contendrá los servicios del motor de Inteligencia Artificial para el
procesamiento de preguntas en lenguaje natural y extracción de respuestas clínicas
y estadísticas a partir de la base de datos de CARDIOUNEMI.

DECISIÓN DE ARQUITECTURA PENDIENTE:
Existen dos alternativas para el acceso del bot a la base de datos:
1. Funciones deterministas / Herramientas con el ORM de Django:
   - Ventajas: Mayor control de seguridad, tipado seguro, prevención de consultas
     arbitrarias o pesadas, fácil de testear con tests unitarios.
   - Desventajas: Menor flexibilidad; el asistente solo puede responder preguntas
     previamente modeladas en funciones de consulta.
2. Generación dinámica de SQL contra un usuario PostgreSQL de solo lectura:
   - Ventajas: Flexibilidad analítica total para responder consultas ad-hoc y correlaciones
     epidemiológicas complejas.
   - Desventajas: Requiere un rol de base de datos estrictamente limitado (GRANT SELECT)
     y validación sintáctica/semántica previa para prevenir inyecciones o sobrecargas.

SEGURIDAD Y SANITIZACIÓN:
Cuando el asistente interactúe con datos reales y endpoints en vivo, las respuestas
renderizadas con Markdown deberán ser saneadas con DOMPurify antes de su inserción
en el DOM para prevenir vulnerabilidades de Cross-Site Scripting (XSS).
"""
