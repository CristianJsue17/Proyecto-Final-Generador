import tkinter as tk
from tkinter import scrolledtext, messagebox
import re
import os
from datetime import datetime

def parse_sql(sql_code):
    columns_search = re.findall(r'(\w+)\s+(\w+)(\((\d+),?(\d+)?\))?(\s+NOT NULL)?', sql_code)
    return columns_search


def generate_migration_code(sql_code, table_name):
    columns = parse_sql(sql_code)
    table_name_plural = f"{table_name}s"
    migration_code = f"""<?php

use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

class Create{table_name_plural.capitalize()}Table extends Migration
{{
    public function up():void
    {{
        Schema::create('suppliers', function (Blueprint $table) {{
            $table->id();
"""
    for column in columns:
        column_name, data_type, _, length, decimal, not_null = column
        
        # Check if the data type is 'Numeric' and the column name is 'LIMITECREDITO', if so, change the data type to 'decimal'
        if 'numeric' in data_type.lower() and column_name.upper() == 'LIMITECREDITO':
            data_type = 'decimal'
        else:
            data_type = 'string' if 'varchar' in data_type.lower() else data_type
        
        nullable = '->nullable()' if 'NOT NULL' not in not_null else ''
        migration_code += f"            $table->{data_type}('{column_name}'"
        
        if length:
            migration_code += f", {length}"
        if decimal:
            migration_code += f", {decimal}"
        
        migration_code += f"){nullable};\n"
    
    migration_code += "            $table->timestamps();\n        });\n    }\n\n    public function down():void\n    {\n        Schema::dropIfExists('proveedores');\n    }\n}\n?>"
    return migration_code



def generate_model_code(table_name, sql_code):
    columns = parse_sql(sql_code)
    model_name = table_name.capitalize()
    fields = ",\n        ".join([f"'{column[0]}'" for column in columns])  # Cambiado para separar con comas y nuevas líneas
    model_code = f"""<?php

namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;

class {model_name} extends Model
{{
    use HasFactory;

    protected $fillable = [
        {fields}
    ];
}}
"""
    return model_code


def generate_controller_code(table_name, sql_code):
    columns = parse_sql(sql_code)
    model_name = table_name.capitalize()
    controller_name = f"{model_name}Controller"
    validation_rules = []

    for column in columns:
        column_name, data_type, _, length, decimal, not_null = column
        rule_parts = []
        
        if 'NOT NULL' in not_null or column_name.lower() in ['ruc', 'razonsocial']:
            rule_parts.append("required")
        else:
            rule_parts.append("nullable")
        
        if 'varchar' in data_type.lower() or 'char' in data_type.lower():
            rule_parts.append(f"max:{length}")
        elif 'integer' in data_type.lower():
            rule_parts.append("integer")
        elif 'numeric' in data_type.lower() or 'decimal' in data_type.lower():
            rule_parts.append("numeric")
            if length and decimal and column_name.lower() != 'limitecredito':
                rule_parts.append(f"digits:{length}")
                rule_parts.append(f"decimal:{decimal}")

        if column_name.lower() == 'ruc':
            rule_parts.append("unique:suppliers")
        
        if column_name.lower() == 'email':
            rule_parts.append("email")

        if column_name.lower() == 'fecha':
            rule_parts.append("date")
        
        # Construct the final validation string for the column
        validation_rules.append(f"'{column_name}' => '{'|'.join(rule_parts)}',")  # Se añade una coma al final de cada regla

    validation_rules_string = "\n            ".join(validation_rules)

    controller_code = f"""<?php

namespace App\\Http\\Controllers;

use App\\Models\\{model_name};
use Illuminate\\Http\\Request;

class {controller_name} extends Controller
{{
    public function index()
    {{
        $proveedores = {model_name}::paginate(5);
        return view('proveedores.index', compact('proveedores'));
    }}

    public function create()
    {{
        return view('proveedores.create');
    }}

    public function store(Request $request)
    {{
        $validatedData = $request->validate([
            {validation_rules_string}
        ]);

        {model_name}::create($validatedData);
        return redirect()->route('proveedores.create')->with('success', 'Proveedor registrado con exito.');
    }}

    public function edit({model_name} $proveedor)
    {{
        return view('proveedores.edit', compact('proveedor'));
    }}

    public function update(Request $request, {model_name} $proveedor)
    {{
        $proveedor->update($request->all());
        return redirect()->route('proveedores.index')->with('success', 'Proveedor actualizado con exito.');
    }}

    public function destroy({model_name} $proveedor)
    {{
        $proveedor->delete();
        return redirect()->route('proveedores.index')->with('success', 'Proveedor eliminado con exito.');
    }}
}}
"""
    return controller_code



def generate_views(table_name, columns):
    # Capitalize and make placeholders human-friendly
    def format_label(column_name):
        return column_name.replace('_', ' ').capitalize()

    create_fields_html = '\n'.join([
        f"""        <div class="col-md-6">
            <label for="{col[0]}">{format_label(col[0])}:</label>
            <input type="text" class="form-control" id="{col[0]}" name="{col[0]}" placeholder="Ingrese {format_label(col[0])}" required>
        </div>""" for col in columns
    ])

    edit_fields_html = '\n'.join([
        f"""        <div class="col-md-6">
            <label for="{col[0]}">{format_label(col[0])}:</label>
            <input type="text" class="form-control" id="{col[0]}" name="{col[0]}" value="{{{{ $proveedor->{col[0]} }}}}" required>
        </div>""" for col in columns
    ])

    headers_index = '\n'.join([f"                <th>{format_label(col[0])}</th>" for col in columns])
    rows_index = '\n'.join([f"                    <td>{{{{ $proveedor->{col[0]} }}}}</td>" for col in columns])

    create_view_code = f"""@extends('adminlte::page')

@section('title', 'Registrar Proveedor')

@section('content_header')
    <h1>Registrar Proveedor</h1>
@stop

@section('content')
    
    @if ($errors->any())
        <div class="alert alert-danger">
            <ul>
                @foreach ($errors->all() as $error)
                    <li>{{{{ $error }}}}</li>
                @endforeach
            </ul>
        </div>
    @endif

    
    @if (Session::get('success'))
        <div class="alert alert-success">
        {{{{ Session::get('success') }}}}
        </div>
    @endif

@section('content')
    
    <form action="{{{{ route('proveedores.store') }}}}" method="POST" autocomplete="off">
        @csrf
{create_fields_html}
        <br>
        <button type="submit" class="btn btn-primary">Registrar</button>
    </form>
@stop
"""

    edit_view_code = f"""@extends('adminlte::page')

@section('title', 'Editar Proveedor')

@section('content_header')
    <h1 class="m-0 text-dark">Editar Proveedor</h1>
@endsection

@section('content')
<div class="container mt-3">
    <div class="row">
     <div class="col-md-6">
    <form action="{{{{ route('proveedores.update', ['proveedor' => $proveedor->id]) }}}}" method="POST">
        @csrf
        @method('PUT')
{edit_fields_html}
        <br>
        <button type="submit" class="btn btn-success">Actualizar</button>
    </form>
 </div>
</div>
</div>
@endsection
"""

    index_view_code = f"""@extends('adminlte::page')

@section('title', 'Lista de Proveedores')

@section('content_header')
    <h1 class="m-0 text-dark">Lista de Proveedores</h1>
@stop

@section('content')
    <table class="table table-bordered">
        <thead>
            <tr>
{headers_index}                
                <th>Acciones</th>
            </tr>
        </thead>
        <tbody>
            @foreach ($proveedores as $proveedor)
                <tr>
{rows_index}
                    <td>
                        <a href="{{{{ route('proveedores.edit', $proveedor->id) }}}}" class="btn btn-warning btn-sm mr-1">Editar</a>
                        <form action="{{{{ route('proveedores.destroy', $proveedor->id) }}}}" method="POST" onsubmit="return confirm('¿Esta seguro de que desea eliminar este elemento?');">
                            @csrf
                            @method('DELETE')
                            <button type="submit" class="btn btn-danger btn-sm">Eliminar</button>
                        </form>
                    </td>
                </tr>
            @endforeach
        </tbody>
    </table>
    {{{{ $proveedores->links() }}}}
@stop
"""

    return create_view_code, edit_view_code, index_view_code



def generate_web_routes_code(existing_content):
    # Define el nombre del archivo que será guardado en el escritorio
    new_web_php_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'web_routes.txt')

    # Nuevo contenido que se añadirá después del bloque PHP
    new_use_statement = "use App\\Http\\Controllers\\SupplierController;\n"
    new_routes_content = """
Auth::routes(['register' => true]); // Assuming you want to disable registration.

Route::middleware(['auth'])->group(function () {
    Route::get('home', [App\Http\Controllers\HomeController::class, 'index'])->name('home');
    Route::delete('/proveedores/{proveedor}', [SupplierController::class, 'destroy'])->name('proveedores.destroy');
    Route::get('/proveedores', [SupplierController::class, 'index'])->name('proveedores.index');
    Route::get('/proveedores/{proveedor}/edit', [SupplierController::class, 'edit'])->name('proveedores.edit');
    Route::get('/proveedores/create', [SupplierController::class, 'create'])->name('proveedores.create');
    Route::post('/proveedores', [SupplierController::class, 'store'])->name('proveedores.store');
    Route::put('/proveedores/{proveedor}', [SupplierController::class, 'update'])->name('proveedores.update');
});

//REEMPLAZA ESTE CODIGO EN TU ARCHIVO web.php
//UBICADO EN: 'tu_carpeta_proyecto'/routes/web.php
"""

    # Encuentra la posición después de la apertura de PHP
    php_open_tag = "<?php\n"
    position_after_php_open_tag = existing_content.find(php_open_tag) + len(php_open_tag)

    # Inserta el nuevo use statement después de la apertura de PHP
    updated_content = existing_content[:position_after_php_open_tag] + new_use_statement + existing_content[position_after_php_open_tag:]

    # Añade el nuevo contenido de rutas al final
    final_content = updated_content + new_routes_content

    # Guarda el contenido final en un nuevo archivo .txt
    with open(new_web_php_path, 'w') as new_file:
        new_file.write(final_content)

    # Muestra un mensaje con la ubicación del archivo guardado
    messagebox.showinfo("Archivo Guardado", f"El archivo web_routes.txt se ha guardado en: USERPERFILE")



def generate_adminlte_fragment():
    adminlte_fragment_content = """/* PARA AGREGAR VISUALIZACION DE LAS 2 OPCIONES 
    (REGISTRAR PROVEEDOR y LISTAR PROVEEDOR) VE A LA RUTA
    'tu_carpeta_proyecto'/config/adminlte.php
    
    Buscas dentro del archivo la fila que dice 'menu' => [
    ubicado generalmente por la fila 280
    y antes que cierre el corchete " ], " pegas esas lineas codigo:
        
        [
            'text' => 'Registrar Proveedor',
            'url'  => 'proveedores/create',
            'icon' => 'fas fa-fw fa-user-plus',
        ],
        [
            'text' => 'Listar Proveedores',
            'url' => 'proveedores',
            'icon' => 'fas fa-fw fa-list',
        ],
    
    
        Y CTRL+S PARA GUARDAR */
    """
    adminlte_fragment_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'adminlte_fragment.txt')
    
    with open(adminlte_fragment_path, 'w') as f:
        f.write(adminlte_fragment_content)
    
    messagebox.showinfo("Archivo Guardado", f"El archivo adminlte_fragment.txt se ha guardado en: {adminlte_fragment_path}")
    # Actualiza el estado en la interfaz de usuario
    adminlte_status_label.config(text="Fragmento archivo AdminLTE.php - Estado: 'Generado'")



def save_files(laravel_app_path, table_name, sql_code):
    migration_code = generate_migration_code(sql_code, table_name)
    model_code = generate_model_code(table_name, sql_code)
    controller_code = generate_controller_code(table_name, sql_code)
    sql_code = sql_input.get("1.0", tk.END).strip()
    columns = parse_sql(sql_code)
    create_view_code, edit_view_code, index_view_code = generate_views(table_name, columns)

    # Defining paths
    migration_path = os.path.join(laravel_app_path, "database/migrations")
    model_path = os.path.join(laravel_app_path, "app/Models")
    controller_path = os.path.join(laravel_app_path, "app/Http/Controllers")
    views_path = os.path.join(laravel_app_path, f"resources/views/{table_name}s")

    # Creating directories if they don't exist
    for path in [migration_path, model_path, controller_path, views_path]:
        os.makedirs(path, exist_ok=True)
    
    # Saving files
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    with open(os.path.join(migration_path, f"{timestamp}_create_{table_name}s_table.php"), 'w') as f:
        f.write(migration_code)
    with open(os.path.join(model_path, f"{table_name.capitalize()}.php"), 'w') as f:
        f.write(model_code)
    with open(os.path.join(controller_path, f"{table_name.capitalize()}Controller.php"), 'w') as f:
        f.write(controller_code)
    with open(os.path.join(views_path, "create.blade.php"), 'w') as f:
        f.write(create_view_code)
    with open(os.path.join(views_path, "edit.blade.php"), 'w') as f:
        f.write(edit_view_code)
    with open(os.path.join(views_path, "index.blade.php"), 'w') as f:
        f.write(index_view_code)

    messagebox.showinfo("Success", "Files generated successfully.")
def generate_files():
    laravel_app_path = app_path_entry.get().strip()
    sql_code = sql_input.get("1.0", tk.END).strip()
    table_name = table_name_entry.get().strip()
    
    laravel_app_path = app_path_entry.get().strip()
    sql_code = sql_input.get("1.0", tk.END).strip()
    table_name = table_name_entry.get().strip()
    
    
    
    existing_content = existing_web_content_input.get("1.0", tk.END)
    generate_web_routes_code(existing_content)

    generate_adminlte_fragment()

    if not laravel_app_path:
        messagebox.showerror("Error", "Laravel application path is required.")
        return
    if not table_name:
        messagebox.showerror("Error", "Table name is required.")
        return
    if not sql_code:
        messagebox.showerror("Error", "SQL code is required.")
        return

    try:
        save_files(laravel_app_path, table_name, sql_code)
        messagebox.showinfo("Success", "All files have been generated successfully.")
    except Exception as e:
        messagebox.showerror("Error", str(e))
    
    

# UI setup
root = tk.Tk()
root.title("Laravel File Generator")

tk.Label(root, text="Ubicación Laravel Application:").pack(padx=5, pady=5)
app_path_entry = tk.Entry(root, width=50)
app_path_entry.pack(padx=5, pady=5)

tk.Label(root, text="Nombre Tabla (Singular):").pack(padx=5, pady=5)
table_name_entry = tk.Entry(root, width=50)
table_name_entry.pack(padx=5, pady=5)

tk.Label(root, text="Coloca código SQL CREATE TABLE:").pack(padx=5, pady=5)
sql_input = scrolledtext.ScrolledText(root, height=10, width=50)
sql_input.pack(padx=5, pady=5)



tk.Label(root, text="Generador web.php (Empezar <?php)- Busca archivo carpeta 'routes'").pack(padx=5, pady=5)
existing_web_content_input = scrolledtext.ScrolledText(root, height=10, width=50)
existing_web_content_input.pack(padx=5, pady=5)


adminlte_status_label = tk.Label(root, text="Fragmento archivo AdminLTE.php - Estado: 'No Generado'")
adminlte_status_label.pack(padx=5, pady=5)

generate_button = tk.Button(root, text="Generate Files", command=generate_files)
generate_button.pack(pady=20)

root.mainloop()
