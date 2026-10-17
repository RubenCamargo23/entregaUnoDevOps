from app import create_app

# AWS Elastic Beanstalk (plataforma Python) busca por defecto el objeto WSGI "application" en application.py
application = create_app()

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=8000, debug=True)
