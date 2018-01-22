def search(dirname):
    filenames = os.listdir(dirname)
    for filename in filenames:
        full_filename = os.path.join(dirname,filename)
        full_dirname = os.path.join(dirname)
        if os.path.isdir(full_filename):
            search(full_filename)
            
            
