# ##########################################################################################
# # setup db
# ##########################################################################################
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://%s:%s@localhost/%s' % (localConfig.MYSQL_USERNAME, localConfig.MYSQL_PASSWORD, localConfig.MYSQL_DATABASE ) 
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config['SQLALCHEMY_POOL_SIZE'] = 1
# db = SQLAlchemy(app)