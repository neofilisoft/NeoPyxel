from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

hiddenimports = collect_submodules("lupa")
datas = collect_data_files("lupa")
binaries = collect_dynamic_libs("lupa")
