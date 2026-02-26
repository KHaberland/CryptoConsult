"""
Единый источник версии приложения CryptoConsult.
Используется в интерфейсе, логах, сборке и установщике.

Пример для установщика (PyInstaller, Inno Setup и т.п.):
    python -c "from version import __version__; print(__version__)"
Или в скрипте сборки: CryptoConsult-Setup-v{__version__}.exe
"""

__version__ = "1.0.0"
