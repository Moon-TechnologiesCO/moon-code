# 🌙 Moon Code

Editor de código para la terminal, con explorador de archivos, pestañas, temas Moon y chat de IA local (Ollama).

## Instalar y ejecutar

```bash
cd /home/jdca/Desktop/MoonCode
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m moon [carpeta] [--nerd]
```

`--nerd` usa iconos de Nerd Font; sin él se muestran emoji.

## Atajos

| Tecla | Acción |
|---|---|
| ctrl+s | Guardar |
| ctrl+w | Cerrar pestaña |
| ctrl+b | Mostrar/ocultar explorador |
| ctrl+a | Mostrar/ocultar chat IA |
| ctrl+t | Cambiar tema (noche/día) |
| ctrl+p | Paleta de comandos |
| ctrl+q | Salir |

## IA local

Moon Code habla con Ollama en `http://localhost:11434`.
Modelo por defecto: `gemma3n:e2b`. Cámbialo con `MOON_MODEL=deepseek-r1:7b`.

## Pendiente

- Autocompletado y LSP (pyright, tsserver).
- Terminal integrada.
- Búsqueda difusa de archivos.
