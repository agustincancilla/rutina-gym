# Rutina de Gym

App de la rutina de gimnasio de Agus: https://agustincancilla.github.io/rutina-gym/

- Dos rutinas: **Volumen** (lun pecho y bíceps, mar hombros, mié piernas, vie espalda y tríceps) y **Definición** (lun, mié, vie full body). Abre en el día que toca hoy (o el próximo).
- Pestaña Rutina: cada ejercicio con peso, series × repes y etiquetas (Bilbo, Rest pause, Drop set…); "Anotar series" guarda kilos y repes de la primera serie (las demás van con el mismo peso) y el peso grande y las repes de la tarjeta pasan a ser esos; muestra "Última vez". "Editar orden y día": reordenar, cambiar el día (si choca, se intercambian), editar/borrar/agregar.
- Pestaña Bilbo (máquina de pecho, press de banca, sentadilla): serie a la mitad del RM al fallo; +2,5 kg por semana mientras haga más de 15 repes; con 15 o menos, probar RM y empezar ciclo nuevo. Gráfico del ciclo e historial.
- Descanso: botones **3:00 Serie** y **5:00 Bilbo**. Mantiene la pantalla prendida, suena y vibra.
- Pesos en **total** (no "por lado"), salvo unilaterales, que van "c/lado". Mismos nombres de ejercicio en Volumen y Definición.
- Clave en el celu: `rutina-gym-v1`.

## Cómo trabajar con Agus

- Todo lo que se le muestre va en español rioplatense. Solo quedan en inglés nombres de comandos y archivos.
- Agus no es programador: explicar en pocas líneas qué se va a hacer antes de un cambio grande y esperar su OK; los pasos que tenga que hacer él, uno por uno.
- Muchas veces trabaja desde el celu (sesión en la nube): no hay acceso a sus datos ni a otros repos.

## Cómo está hecha

App web instalable (PWA) que anda sin internet, en GitHub Pages. Este repo es **público**: nunca subir datos personales (el `.gitignore` bloquea los `.json` salvo el manifest).

- `index.html` tiene todo el HTML, CSS y JS. `manifest.webmanifest`, `sw.js`, `icons/`.
- Rutas relativas (la app vive en `agustincancilla.github.io/<repo>/`).
- Los datos viven solo en el `localStorage` del celu. Botón "Datos y copias" para descargar/cargar copias. "Guardar en Drive o mail" (`shareBackup`) abre el menú de compartir del celu con la copia como `.txt` (Chrome no deja compartir `.json`); el botón "Hacer copia" del aviso de 30 días va directo ahí. Cargar datos acepta `.json` y `.txt`.
- Fechas con la fecha **local** (no `toISOString()`, que en Argentina después de las 21 h da el día siguiente).

## Al cambiar algo

1. Cambiar `index.html`.
2. **Subir `VERSION` en `sw.js`** (`v1` → `v2`…), si no el celu sigue mostrando la vieja.
3. Si cambia la forma de los datos, que `normalize()` siga aceptando las copias viejas: Agus tiene datos cargados que no se pueden perder.
4. Commit (terminar el mensaje con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`) y push a `main`.
5. Avisarle: el celu baja la versión nueva cuando tiene internet y la muestra **la segunda vez** que abre la app.

