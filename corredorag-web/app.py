from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def inicio():
    # Le decimos a Python que busque y muestre el archivo index.html
    return render_template('index.html')

if __name__ == '__main__':
    # debug=True reinicia el servidor automáticamente al guardar cambios
    app.run(debug=True)