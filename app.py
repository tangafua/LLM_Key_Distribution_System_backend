import logging
import secrets
from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, unset_jwt_cookies
from flask_cors import CORS
import time
import openai
from zhipuai import ZhipuAI
from transformers import AutoTokenizer


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB'] = 'apisystem'

mysql = MySQL(app)

# JWT configurations
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # 更改此项为你的密钥
app.config['JWT_TOKEN_LOCATION'] = ['headers']  # 确保从 headers 获取 token
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # 禁用 token 过期时间

jwt = JWTManager(app)

tokenizer = AutoTokenizer.from_pretrained("llama-7b-hf")


# 定义User模型
class User:
    def __init__(self, user_id, user_name, user_password, user_phone, user_email, balance):
        self.user_id = user_id
        self.user_name = user_name
        self.user_password = user_password
        self.user_phone = user_phone
        self.user_email = user_email
        self.balance = balance


# 普通用户登录
@app.route('/user_login', methods=['POST'])
def user_login():
    try:
        user_name = request.json.get('user_name')
        user_password = request.json.get('user_password')
        if not user_name or not user_password:
            return jsonify({'status': 0, 'msg': '请填写完整信息', 'data': {}}), 400

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM user WHERE user_name = %s", (user_name,))
        user = cur.fetchone()
        print(user)
        cur.close()
        if not user:
            return jsonify({'status': 0, 'msg': '没有此用户', 'data': {}}), 404
        stored_password = user[2]
        if stored_password == user_password:
            access_token = create_access_token(identity={'user_id': user[0], 'user_name': user_name})
            return jsonify({'status': 1, 'msg': '登录成功', 'data': {'access_token': access_token, 'user_id': user[0], 'user_name': user_name}})
        else:
            return jsonify({'status': 0, 'msg': '用户名或密码错误', 'data': {}}), 401

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': {}}), 500


# 定义User模型
class Admin:
    def __init__(self, admin_id, admin_name, admin_password, admin_phone, admin_email):
        self.admin_id = admin_id
        self.admin_name = admin_name
        self.admin_password = admin_password
        self.admin_phone = admin_phone
        self.admin_email = admin_email


# 管理员登录
@app.route('/admin_login', methods=['POST'])
def admin_login():
    try:
        admin_name = request.json.get('admin_name')
        admin_password = request.json.get('admin_password')
        if not admin_name or not admin_password:
            return jsonify({'status': 0, 'msg': '请填写完整信息', 'data': {}}), 400

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin WHERE admin_name = %s", (admin_name,))
        admin = cur.fetchone()
        print(admin)
        cur.close()
        if not admin:
            return jsonify({'status': 0, 'msg': '没有此用户', 'data': {}}), 404
        stored_password = admin[2]
        if stored_password == admin_password:
            access_token = create_access_token(identity=admin_name)
            return jsonify({'status': 1, 'msg': '登录成功', 'data': {'access_token': access_token, 'admin_name': admin_name}})
        else:
            return jsonify({'status': 0, 'msg': '用户名或密码错误', 'data': {}}), 401

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': {}}), 500


# 普通用户注册
@app.route('/user_register', methods=['POST'])
def register():
    data = request.get_json()
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO user (user_name, user_password, user_email, user_phone, balance) VALUES (%s, %s, %s, %s, %s)",
                (data['user_name'], data['user_password'], data['user_email'], data['user_phone'], 0))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 1, 'msg': '注册成功', 'data': {}}), 200


# 普通用户给账户充钱
@app.route('/topup', methods=['POST'])
@jwt_required()
def topup():
    try:
        data = request.get_json()
        money = data.get('money')
        user_name = data.get('user_name')
        cur = mysql.connection.cursor()
        cur.execute("SELECT balance FROM user WHERE user_name = %s", (user_name,))
        current_balance = cur.fetchone()[0]
        new_balance = current_balance + money
        cur.execute("UPDATE user SET balance = %s WHERE user_name = %s", (new_balance, user_name))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'msg': '充值成功', 'data': {'balance': new_balance}})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误'}), 500


# 读取普通用户账户余额
@app.route('/money', methods=['GET'])
@jwt_required()
def get_money():
    try:
        identity = get_jwt_identity()
        user_id = identity['user_id']
        # user_name = get_jwt_identity()
        cur = mysql.connection.cursor()
        cur.execute("SELECT balance FROM user WHERE user_id = %s", (user_id,))
        balance = cur.fetchone()[0]
        cur.close()
        return jsonify({'status': 1, 'msg': '获取余额成功', 'data': {'balance': balance}})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误'}), 500


# 登出
@app.route('/logout', methods=['POST'])
@jwt_required()
def user_logout():
    response = jsonify({'status': 1, 'msg': '登出成功', 'data': {}})
    unset_jwt_cookies(response)
    return response


# 管理员添加模型
@app.route('/admin_addModel', methods=['POST'])
def addModel():
    try:
        data = request.get_json()
        model_name = data.get('model_name')
        model_status = int(data.get('model_status'))
        model_price = data.get('model_price')
        model_description = data.get('model_description')
        if not model_name or not model_price or not model_description:
            return jsonify({'status': 0, 'msg': '请填写完整的模型信息', 'data': {}}), 400
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO model (model_name, model_status, model_price, model_description) VALUES (%s, %s, %s, %s)",
                    (model_name, model_status, model_price, model_description))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'msg': '模型添加成功', 'data': {}}), 200
    except KeyError as e:
        return jsonify({'status': 0, 'msg': f'缺少必要字段 {str(e)}', 'data': {}}), 400
    except Exception as e:
        print(f"Error in addModel route: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': {}}), 500

# 管理员修改模型
@app.route('/admin_editModel', methods=['PUT'])
def editModel():
    try:
        data = request.get_json()
        model_id = data.get('model_id')
        model_name = data.get('model_name')
        model_status = int(data.get('model_status'))
        model_price = data.get('model_price')
        model_description = data.get('model_description')
        cur = mysql.connection.cursor()
        cur.execute("UPDATE model SET model_name = %s, model_status = %s, model_price = %s, model_description = %s WHERE model_id = %s",
                    (model_name, model_status, model_price, model_description, model_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'msg': '模型修改成功', 'data': {}}), 200
    except Exception as e:
        print(f"Error in editModel route: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': {}}), 500


# 管理员删除模型
@app.route('/admin_delModel', methods=['DELETE'])
def delModel():
    try:
        model_id = request.args.get('model_id')
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM model WHERE model_id = %s", (model_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'message': '模型删除成功'})
    except Exception as e:
        print(f"Error in delModel route: {e}")
        return jsonify({'status': 0, 'message': str(e)})


# 管理员删除卡段
@app.route('/admin_delCard', methods=['DELETE'])
def delCard():
    try:
        card_id = request.args.get('card_id')
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM card WHERE card_id = %s", (card_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'message': '卡段删除成功'}), 200
    except Exception as e:
        print(f"Error in delModel route: {e}")
        return jsonify({'status': 0, 'message': str(e)}), 500


# 管理员禁用卡段
@app.route('/admin_forbidCard', methods=['PUT'])
def forbidCard():
    try:
        card_id = request.json.get('card_id')
        cur = mysql.connection.cursor()
        cur.execute("UPDATE card SET card_status = 0 WHERE card_id = %s", (card_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'message': '卡段已成功禁用'}), 200
    except Exception as e:
        print(f"Error in forbidCard route: {e}")
        return jsonify({'status': 0, 'message': str(e)}), 500


# 管理员启用卡段
@app.route('/admin_activeCard', methods=['PUT'])
def activeCard():
    try:
        card_id = request.json.get('card_id')
        cur = mysql.connection.cursor()
        cur.execute("UPDATE card SET card_status = 1 WHERE card_id = %s", (card_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'message': '卡段已成功启用'}), 200
    except Exception as e:
        print(f"Error in activeCard route: {e}")
        return jsonify({'status': 0, 'message': str(e)}), 500


# 获取普通用户信息
@app.route('/user_info', methods=['GET'])
@jwt_required()
def get_user_info():
    try:
        identity = get_jwt_identity()
        user_id = identity['user_id']
        # user_name = get_jwt_identity()
        cur = mysql.connection.cursor()
        cur.execute("SELECT user_id, user_name, user_password, user_email, user_phone FROM user WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        print(user)
        cur.close()
        if not user:
            return jsonify({'status': 0, 'msg': '用户不存在', 'data': {}}), 404
        user_info = {
            'user_id': user[0],
            'user_name': user[1],
            'user_password': user[2],
            'user_email': user[3],
            'user_phone': user[4]
        }
        return jsonify({'status': 1, 'msg': '成功获取用户信息', 'data': user_info})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': {}}), 500


# 编辑普通用户个人信息
@app.route('/edit_user_info', methods=['POST'])
@jwt_required()
def edit_user_info():
    try:
        data = request.get_json()
        identity = get_jwt_identity()
        user_name = identity['user_name']
        user_password = data.get('user_password')
        user_phone = data.get('user_phone')
        user_email = data.get('user_email')

        cur = mysql.connection.cursor()
        cur.execute("UPDATE user SET user_password = %s, user_phone = %s, user_email = %s WHERE user_name = %s",
                    (user_password, user_phone, user_email, user_name))
        mysql.connection.commit()
        cur.close()

        return jsonify({'status': 1, 'msg': '信息更新成功'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误'}), 500


# 获取管理员信息
@app.route('/admin_info', methods=['GET'])
@jwt_required()
def get_admin_info():
    try:
        admin_name = get_jwt_identity()
        cur = mysql.connection.cursor()
        cur.execute("SELECT admin_id, admin_name, admin_password, admin_email, admin_phone FROM admin WHERE admin_name = %s", (admin_name,))
        admin = cur.fetchone()
        print(admin)
        cur.close()
        if not admin:
            return jsonify({'status': 0, 'msg': '用户不存在', 'data': {}}), 404
        admin_info = {
            'admin_id': admin[0],
            'admin_name': admin[1],
            'admin_password': admin[2],
            'admin_email': admin[3],
            'admin_phone': admin[4]
        }
        return jsonify({'status': 1, 'msg': '成功获取用户信息', 'data': admin_info})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': {}}), 500


# 编辑管理员个人信息
@app.route('/edit_admin_info', methods=['POST'])
@jwt_required()
def edit_admin_info():
    try:
        data = request.get_json()
        admin_name = get_jwt_identity()
        admin_password = data.get('admin_password')
        admin_phone = data.get('admin_phone')
        admin_email = data.get('admin_email')
        cur = mysql.connection.cursor()
        cur.execute("UPDATE admin SET admin_password = %s, admin_phone = %s, admin_email = %s WHERE admin_name = %s",
                    (admin_password, admin_phone, admin_email, admin_name))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'msg': '信息更新成功'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误'}), 500


# 定义Model模型
class Model:
    def __init__(self, model_id, model_name, model_status, model_price, model_description):
        self.model_id = model_id
        self.model_name = model_name
        self.model_status = model_status
        self.model_price = model_price
        self.model_description = model_description


# 获取所有模型列表
@app.route('/allModels', methods=['GET'])
def get_all_models():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT model_id, model_name, model_status, model_price, model_description FROM model")
        models = cur.fetchall()
        cur.close()
        if not models:
            return jsonify({'status': 0, 'msg': '没有模型数据', 'data': []})
        model_list = [
            {
                'model_id': model[0],
                'model_name': model[1],
                'model_status': model[2],
                'model_price': model[3],
                'model_description': model[4]
            } for model in models
        ]
        return jsonify({'status': 1, 'msg': '成功获取模型列表', 'data': model_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


# 根据模型名称和状态搜索模型
@app.route('/searchModel', methods=['GET'])
def search_model():
    model_name = request.args.get('model_name', '').strip()
    model_status = request.args.get('model_status', '').strip()
    query = "SELECT model_id, model_name, model_status, model_price, model_description FROM model WHERE 1=1"
    params = []
    if model_name:
        query += " AND model_name LIKE %s"
        params.append(f"%{model_name}%")
    if model_status:
        query += " AND model_status = %s"
        params.append(model_status)
    try:
        cur = mysql.connection.cursor()
        cur.execute(query, tuple(params))
        models = cur.fetchall()
        cur.close()
        if not models:
            return jsonify({'status': 0, 'msg': '没有找到符合条件的模型', 'data': []})
        model_list = [
            {
                'model_id': model[0],
                'model_name': model[1],
                'model_status': model[2],
                'model_price': model[3],
                'model_description': model[4]
            } for model in models
        ]
        return jsonify({'status': 1, 'msg': '成功查询模型', 'data': model_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500

# 定义Card模型
class Card:
    def __init__(self, card_id, user_id, user_name, api_key, balance, card_status):
        self.card_id = card_id
        self.user_id = user_id
        self.user_name = user_name
        self.api_key = api_key
        self.balance = balance
        self.card_status = card_status


# 获取所有卡段列表
@app.route('/admin_allCards', methods=['GET'])
def get_all_cards():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT card_id, user_id, user_name, api_key, left_balance, card_status FROM card")
        cards = cur.fetchall()
        cur.close()
        if not cards:
            return jsonify({'status': 0, 'msg': '没有卡段数据', 'data': []})
        card_list = [
            {
                'card_id': card[0],
                'user_id': card[1],
                'user_name': card[2],
                'api_key': card[3],
                'balance': card[4],
                'card_status': card[5]
            } for card in cards
        ]
        return jsonify({'status': 1, 'msg': '成功获取卡段列表', 'data': card_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


# 根据用户名和卡段状态搜索卡段
@app.route('/admin_searchCard', methods=['GET'])
def search_card():
    user_name = request.args.get('user_name', '').strip()
    card_status = request.args.get('card_status', '').strip()
    query = "SELECT card_id, user_id, user_name, api_key, left_balance, card_status FROM card WHERE 1=1"
    params = []
    if user_name:
        query += " AND user_name LIKE %s"
        params.append(f"%{user_name}%")
    if card_status:
        query += " AND card_status = %s"
        params.append(card_status)
    try:
        cur = mysql.connection.cursor()
        cur.execute(query, tuple(params))
        cards = cur.fetchall()
        cur.close()
        if not cards:
            return jsonify({'status': 0, 'msg': '没有找到符合条件的卡段', 'data': []})
        card_list = [
            {
                'card_id': card[0],
                'user_id': card[1],
                'user_name': card[2],
                'api_key': card[3],
                'balance': card[4],
                'card_status': card[5]
            } for card in cards
        ]
        return jsonify({'status': 1, 'msg': '成功模型', 'data': card_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


# 定义Record模型
class Record:
    def __init__(self, record_id, user_id, user_name, model_id, card_id, card_name, model_name, token_cost, price_cost):
        self.record_id = record_id
        self.user_id = user_id
        self.user_name = user_name
        self.model_id = model_id
        self.card_id = card_id
        self.card_name = card_name
        self.model_name = model_name
        self.token_cost = token_cost
        self.price_cost = price_cost


# 获取所有使用记录列表
@app.route('/admin_allRecords', methods=['GET'])
def get_all_records():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT record_id, user_id, user_name, model_id, card_id, card_name, model_name, token_cost, price_cost FROM record")
        records = cur.fetchall()
        cur.close()
        if not records:
            return jsonify({'status': 0, 'msg': '没有使用记录数据', 'data': []})
        record_list = [
            {
                'record_id': card[0],
                'user_id': card[1],
                'user_name': card[2],
                'model_id': card[3],
                'card_id': card[4],
                'card_name': card[5],
                'model_name': card[6],
                'token_cost': card[7],
                'price_cost': card[8]
            } for card in records
        ]
        return jsonify({'status': 1, 'msg': '成功获取使用记录列表', 'data': record_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


# 根据用户名和模型名称搜索卡段
@app.route('/admin_searchRecord', methods=['GET'])
def search_record():
    user_name = request.args.get('user_name', '').strip()
    model_name = request.args.get('model_name', '').strip()
    query = "SELECT record_id, user_id, user_name, model_id, card_id, card_name, model_name, token_cost, price_cost FROM record WHERE 1=1"
    params = []
    if user_name:
        query += " AND user_name LIKE %s"
        params.append(f"%{user_name}%")
    if model_name:
        query += " AND model_name LIKE %s"
        params.append(f"%{model_name}%")
    try:
        cur = mysql.connection.cursor()
        cur.execute(query, tuple(params))
        records = cur.fetchall()
        cur.close()
        if not records:
            return jsonify({'status': 0, 'msg': '没有找到符合条件的使用记录', 'data': []})
        record_list = [
            {
                'record_id': record[0],
                'user_id': record[1],
                'user_name': record[2],
                'model_id': record[3],
                'card_id': record[4],
                'card_name': record[5],
                'model_name': record[6],
                'token_cost': record[7],
                'price_cost': record[8]
            } for record in records
        ]
        return jsonify({'status': 1, 'msg': '成功搜索使用记录', 'data': record_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


@app.route('/user_allRecords', methods=['GET'])
@jwt_required()
def get_user_records():
    try:
        identity = get_jwt_identity()
        user_id = identity['user_id']
        cur = mysql.connection.cursor()
        cur.execute("SELECT record_id, model_name, card_name, token_cost, price_cost FROM record WHERE user_id = %s", (user_id,))
        records = cur.fetchall()
        cur.close()

        if not records:
            return jsonify({'status': 0, 'msg': '没有使用记录数据', 'data': []})

        record_list = [
            {
                'record_id': record[0],
                'model_name': record[1],
                'card_name': record[2],
                'token_cost': record[3],
                'price_cost': record[4]
            } for record in records
        ]

        return jsonify({'status': 1, 'msg': '成功获取使用记录列表', 'data': record_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


# 普通用户根据模型名称和卡段名称搜索自己的使用记录
@app.route('/user_searchRecord', methods=['GET'])
@jwt_required()
def user_search_record():
    identity = get_jwt_identity()
    user_name = identity['user_name']
    model_name = request.args.get('model_name', '').strip()
    card_name = request.args.get('card_name', '').strip()
    query = "SELECT record_id, model_name, card_name, token_cost, price_cost FROM record WHERE user_name = %s"
    params = [user_name]

    if model_name:
        query += " AND model_name LIKE %s"
        params.append(f"%{model_name}%")
    if card_name:
        query += " AND card_name LIKE %s"
        params.append(f"%{card_name}%")

    try:
        cur = mysql.connection.cursor()
        cur.execute(query, tuple(params))
        records = cur.fetchall()
        cur.close()

        if not records:
            return jsonify({'status': 0, 'msg': '没有找到符合条件的使用记录', 'data': []})

        record_list = [
            {
                'record_id': record[0],
                'model_name': record[1],
                'card_name': record[2],
                'token_cost': record[3],
                'price_cost': record[4]
            } for record in records
        ]

        return jsonify({'status': 1, 'msg': '成功搜索使用记录', 'data': record_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


# 普通用户根据卡段状态和卡段名称搜索自己的卡段
@app.route('/user_searchCard', methods=['GET'])
@jwt_required()
def user_search_card():
    identity = get_jwt_identity()
    user_name = identity['user_name']
    card_name = request.args.get('card_name', '').strip()
    card_status = request.args.get('card_status', '').strip()
    query = "SELECT card_id, card_name, card_status, used_balance, left_balance FROM card WHERE user_name = %s"
    params = [user_name]
    if card_name:
        query += " AND card_name LIKE %s"
        params.append(f"%{card_name}%")
    if card_status:
        query += " AND card_status = %s"
        params.append(card_status)

    try:
        cur = mysql.connection.cursor()
        cur.execute(query, tuple(params))
        cards = cur.fetchall()
        cur.close()
        if not cards:
            return jsonify({'status': 0, 'msg': '没有找到符合条件的卡段', 'data': []})
        card_list = [
            {
                'card_id': card[0],
                'card_name': card[1],
                'card_status': card[2],
                'used_balance': card[3],
                'left_balance': card[4]
            } for card in cards
        ]

        return jsonify({'status': 1, 'msg': '成功搜索卡段', 'data': card_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


# 普通用户获取本账户所有卡段
@app.route('/user_allCards', methods=['GET'])
@jwt_required()
def get_user_cards():
    # user_name = get_jwt_identity()
    identity = get_jwt_identity()
    user_id = identity['user_id']
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT card_id, card_name, api_key, card_status, used_balance, left_balance FROM card WHERE user_id = %s", (user_id,))
        cards = cur.fetchall()
        cur.close()
        if not cards:
            return jsonify({'status': 0, 'msg': '没有卡段数据', 'data': []})
        card_list = [
            {
                'card_id': card[0],
                'card_name': card[1],
                'api_key': card[2],
                'card_status': card[3],
                'used_balance': card[4],
                'left_balance': card[5]
            } for card in cards
        ]

        return jsonify({'status': 1, 'msg': '成功获取卡段列表', 'data': card_list})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': []}), 500


def invoke_openai(api_key, model_name, messages, stop, max_tokens, temperature, top_p):
    backoff_time = 1
    if 'llama' in model_name:
        openai.api_base = "http://172.22.159.80:7861"
        openai.api_key = api_key
        while True:
            try:
                return openai.ChatCompletion.create(
                    messages=messages,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stop=stop
                )
            except Exception as e:
                print(e, f' Sleeping {backoff_time} seconds...')
                time.sleep(backoff_time)
                backoff_time *= 1.5
    elif 'glm' in model_name:
        model = ZhipuAI(api_key=api_key)
        backoff_time = 1
        while True:
            try:
                return model.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stop=stop
                )
            except Exception as e:
                print(e, f' Sleeping {backoff_time} seconds...')
                time.sleep(backoff_time)
                backoff_time *= 1.5
    else:
        openai.api_key = api_key
        while True:
            try:
                return openai.ChatCompletion.create(
                    messages=messages,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stop=stop
                )
            except Exception as e:
                print(e, f' Sleeping {backoff_time} seconds...')
                time.sleep(backoff_time)
                backoff_time *= 1.5


@app.route("/chat/completions", methods=['POST'])
@jwt_required()
def inference():
    try:
        user_id = get_jwt_identity()['user_id']
        user_name = get_jwt_identity()['user_name']
        para = request.json
        model = para["model"]
        messages = para["messages"]
        stop_words = para.get('stop', [])
        max_new_tokens = para.get('max_tokens', 2048)
        temperature = para.get('temperature', 1.0)
        top_p = para.get('top_p', 1.0)
        headers = request.headers
        api_key = headers.get('authorization').replace('Bearer ', '')

        contents = []
        for message in messages:
            if isinstance(message["content"], str):
                contents.append(message["content"])
        input_tokens_count = 0
        for content in contents:
            input_tokens_count += len(tokenizer.encode(content))
        cur = mysql.connection.cursor()
        query = "SELECT model_id, model_name, model_price FROM model WHERE model_name = %s"
        cur.execute(query, (model,))
        model_details = cur.fetchone()
        model_id = model_details[0]
        model_name = model_details[1]
        model_price = model_details[2]

        query = "SELECT card_id, card_name, left_balance FROM card WHERE api_key = %s"
        cur.execute(query, (api_key,))
        card_details = cur.fetchone()
        card_id = card_details[0]
        card_name = card_details[1]
        left_balance = cur.fetchone()[2]

        query = "SELECT used_balance FROM card WHERE api_key = %s"
        cur.execute(query, (api_key,))
        used_balance = cur.fetchone()[0]

        input_token_cost = input_tokens_count * model_price
        if left_balance < input_token_cost:
            return jsonify({"msg": "Insufficient balance"}), 400

        response = invoke_openai(api_key, model, messages, stop_words, max_new_tokens, temperature, top_p)
        output_tokens_count = len(tokenizer.encode(response.choices[0].message.content))
        token_cost = input_token_cost + output_tokens_count * model_price
        token_count = input_tokens_count + output_tokens_count
        new_left_balance = left_balance - token_cost
        new_used_balance = used_balance + token_cost
        query = "UPDATE card SET left_balance = %s WHERE api_key = %s"
        cur.execute(query, (new_left_balance, api_key))
        query = "UPDATE card SET used_balance = %s WHERE api_key = %s"
        cur.execute(query, (new_used_balance, api_key))
        cur.execute(
            "INSERT INTO card (user_id, user_name, model_id, card_id, card_name, model_name, token_cost, price_cost) VALUES (%s, %s, %s,%s, %s, %s, %s)",
            (user_id, user_name, model_id, card_id, card_name, model_name, token_count, token_cost))
        mysql.connection.commit()
        return jsonify(response)

    except Exception as e:
        logging.exception(str(e))
        print(f"Error: {e}")


# 普通用户添加卡段
@app.route('/addCard', methods=['POST'])
@jwt_required()
def addCard():
    try:
        data = request.get_json()
        card_name = data.get('card_name')
        card_status = int(data.get('card_status'))
        left_balance = data.get('left_balance')
        user_name = get_jwt_identity()['user_name']
        user_id = get_jwt_identity()['user_id']
        if not card_name or not card_status or not left_balance:
            return jsonify({'status': 0, 'msg': '请填写完整的卡段信息', 'data': {}}), 400
        api_key = secrets.token_hex(16)
        used_balance = 0
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO card (user_id, user_name, card_name, api_key, card_status, used_balance, left_balance) VALUES (%s, %s, %s,%s, %s, %s, %s)",
                    (user_id, user_name, card_name, api_key, card_status, used_balance, left_balance))
        query = "SELECT balance FROM user WHERE user_id = %s"
        cur.execute(query, (user_id,))
        balance = cur.fetchone()[0]
        changed_balance = int(balance) - int(left_balance)
        print(changed_balance)
        query = "UPDATE user SET balance = %s WHERE user_id = %s"
        cur.execute(query, (changed_balance, user_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'msg': '卡段添加成功', 'data': {}}), 200

    except KeyError as e:
        return jsonify({'status': 0, 'msg': f'缺少必要字段 {str(e)}', 'data': {}}), 400

    except Exception as e:
        print(f"Error in addCard route: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': {}}), 500


# 普通用户编辑卡段
@app.route('/editCard', methods=['PUT'])
@jwt_required()
def editCard():
    try:
        data = request.get_json()
        print(data)
        card_id = data.get('card_id')
        card_name = data.get('card_name')
        card_status = int(data.get('card_status'))
        new_left_balance = data.get('left_balance')
        user_id = get_jwt_identity()['user_id']
        cur = mysql.connection.cursor()
        query = "SELECT left_balance FROM card WHERE card_id = %s"
        cur.execute(query, (card_id,))
        old_left_balance = cur.fetchone()[0]
        print(old_left_balance)
        cur.execute(
            "UPDATE card SET card_name = %s, card_status = %s, left_balance = %s WHERE card_id = %s",
            (card_name, card_status, new_left_balance, card_id))
        query = "SELECT balance FROM user WHERE user_id = %s"
        cur.execute(query, (user_id,))
        balance = cur.fetchone()[0]
        print(balance)
        if int(old_left_balance) != int(new_left_balance):
            if int(new_left_balance) > int(old_left_balance):
                new_balance = int(balance) - (int(new_left_balance) - int(old_left_balance))
            if int(new_left_balance) < int(old_left_balance):
                new_balance = int(balance) + (int(old_left_balance) - int(new_left_balance))
            query = "UPDATE user SET balance = %s WHERE user_id = %s"
            cur.execute(query, (new_balance, user_id))
            print(new_balance)
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'msg': '卡段修改成功', 'data': {}}), 200
    except Exception as e:
        print(f"Error in editModel route: {e}")
        return jsonify({'status': 0, 'msg': '服务器内部错误', 'data': {}}), 500


# 普通用户删除卡段
@app.route('/delCard', methods=['DELETE'])
@jwt_required()
def user_delCard():
    try:
        card_id = request.args.get('card_id')
        user_id = get_jwt_identity()['user_id']
        cur = mysql.connection.cursor()
        query = "SELECT left_balance FROM card WHERE card_id = %s"
        cur.execute(query, (card_id,))
        left_balance = cur.fetchone()[0]
        print(left_balance)
        query = "SELECT balance FROM user WHERE user_id = %s"
        cur.execute(query, (user_id,))
        balance = cur.fetchone()[0]
        print(balance)
        new_balance = int(balance) + int(left_balance)
        print(new_balance)
        query = "UPDATE user SET balance = %s WHERE user_id = %s"
        cur.execute(query, (new_balance, user_id))
        cur.execute("DELETE FROM card WHERE card_id = %s", (card_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 1, 'message': '卡段删除成功'})
    except Exception as e:
        print(f"Error in delModel route: {e}")
        return jsonify({'status': 0, 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True)