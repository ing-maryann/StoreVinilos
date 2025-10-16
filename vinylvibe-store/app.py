from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'

# Configuración de base de datos - versión simplificada para empezar
# Usa SQLite en lugar de PostgreSQL para facilitar la instalación
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vinylvibe.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Modelos de la Base de Datos
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    orders = db.relationship('Order', backref='user', lazy=True)

class Vinyl(db.Model):
    __tablename__ = 'vinyls'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    artist = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    vinyl_id = db.Column(db.Integer, db.ForeignKey('vinyls.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    
    vinyl = db.relationship('Vinyl', backref='order_items')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rutas principales
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/vinyls')
def get_vinyls():
    vinyls = Vinyl.query.all()
    return jsonify([{
        'id': v.id,
        'title': v.title,
        'artist': v.artist,
        'genre': v.genre,
        'price': v.price,
        'stock': v.stock
    } for v in vinyls])

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'success': False, 'message': 'Email ya registrado'})
        
        user = User(
            name=data['name'],
            email=data['email'],
            password_hash=generate_password_hash(data['password'])
        )
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return jsonify({'success': True, 'user': {'name': user.name, 'role': user.role}})
    
    except Exception as e:
        print(f"Error en registro: {e}")
        return jsonify({'success': False, 'message': 'Error interno del servidor'})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        user = User.query.filter_by(email=data['email']).first()
        
        if user and check_password_hash(user.password_hash, data['password']):
            login_user(user)
            return jsonify({
                'success': True, 
                'user': {'name': user.name, 'role': user.role}
            })
        
        return jsonify({'success': False, 'message': 'Credenciales incorrectas'})
    
    except Exception as e:
        print(f"Error en login: {e}")
        return jsonify({'success': False, 'message': 'Error interno del servidor'})

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/api/add_vinyl', methods=['POST'])
@login_required
def add_vinyl():
    try:
        if current_user.role != 'admin':
            return jsonify({'success': False, 'message': 'No autorizado'})
        
        data = request.get_json()
        vinyl = Vinyl(
            title=data['title'],
            artist=data['artist'],
            genre=data['genre'],
            price=float(data['price']),
            stock=10
        )
        
        db.session.add(vinyl)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Error al agregar vinilo: {e}")
        return jsonify({'success': False, 'message': 'Error al agregar vinilo'})

@app.route('/api/order', methods=['POST'])
@login_required
def create_order():
    try:
        data = request.get_json()
        
        order = Order(
            user_id=current_user.id,
            total=data['total']
        )
        
        db.session.add(order)
        db.session.commit()
        
        for item in data['items']:
            order_item = OrderItem(
                order_id=order.id,
                vinyl_id=item['id'],
                quantity=item['quantity'],
                price=item['price']
            )
            db.session.add(order_item)
            
            # Actualizar stock
            vinyl = Vinyl.query.get(item['id'])
            if vinyl:
                vinyl.stock -= item['quantity']
        
        db.session.commit()
        return jsonify({'success': True, 'order_id': order.id})
    
    except Exception as e:
        print(f"Error en orden: {e}")
        return jsonify({'success': False, 'message': 'Error al procesar orden'})

@app.route('/api/admin/stats')
@login_required
def admin_stats():
    try:
        if current_user.role != 'admin':
            return jsonify({'error': 'No autorizado'})
        
        stats = {
            'users': User.query.count(),
            'vinyls': Vinyl.query.count(),
            'orders': Order.query.count()
        }
        
        return jsonify(stats)
    
    except Exception as e:
        print(f"Error en stats: {e}")
        return jsonify({'error': 'Error interno del servidor'})

def init_db():
    """Inicializar la base de datos con datos de ejemplo"""
    # SOLUCIÓN: Usar contexto de aplicación
    with app.app_context():
        # Crear todas las tablas
        db.create_all()
        print("✅ Tablas de base de datos creadas")
        
        # Crear usuario admin si no existe
        admin = User.query.filter_by(email='admin@vinylvibe.com').first()
        if not admin:
            admin = User(
                name='Administrador',
                email='admin@vinylvibe.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            print("✅ Usuario administrador creado")
        
        # Agregar vinilos de ejemplo si no existen
        if Vinyl.query.count() == 0:
            vinyls = [
                Vinyl(title='Abbey Road', artist='The Beatles', genre='rock', price=899, stock=10),
                Vinyl(title='Kind of Blue', artist='Miles Davis', genre='jazz', price=1200, stock=5),
                Vinyl(title='Thriller', artist='Michael Jackson', genre='pop', price=999, stock=8),
                Vinyl(title='The Dark Side of the Moon', artist='Pink Floyd', genre='rock', price=1100, stock=6),
                Vinyl(title='Random Access Memories', artist='Daft Punk', genre='electronic', price=1050, stock=4),
                Vinyl(title='B.B. King Live at the Regal', artist='B.B. King', genre='blues', price=850, stock=7)
            ]
            
            for vinyl in vinyls:
                db.session.add(vinyl)
            
            print("✅ Vinilos de ejemplo agregados")
        
        db.session.commit()
        print("✅ Base de datos inicializada correctamente")

if __name__ == '__main__':
    print("🎵 Iniciando VinylVibe...")
    print("📦 Inicializando base de datos...")
    
    init_db()
    
    print("🚀 Servidor iniciado en http://localhost:5000")
    print("👤 Admin: admin@vinylvibe.com / admin123")
    print("🛑 Presiona Ctrl+C para detener el servidor")
    
    app.run(debug=True)