from api_routes.admin_routes import admin_bp, developer_bp
from api_routes.auth_routes import auth_bp
from api_routes.discovery_routes import discovery_bp

__all__ = ["admin_bp", "auth_bp", "discovery_bp", "developer_bp"]
