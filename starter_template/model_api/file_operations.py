import os 


def create_file(path, filename):
    try:
        abs_path= os.path.join(path, filename+".html")
        with open(abs_path,'w') as file:
            print(f"File '{abs_path}' created succesfully")
    except Exception as e:
        print(f"Error while creating '{abs_path}'")


def write_file(path, filename, content):

    abs_path= os.path.join(path, filename+".html")
    if os.path.isfile(abs_path):
        try:
            with open(abs_path,'a') as file:
                file.write(content + '\n')
                print(f"Content written in '{filename}'")
        except Exception as e:
            print(f"Error white writing contents in '{filename}'")
    else:
        print(f"Tried to write to a file that doesn't exist. Path {abs_path}")


#Helper functions

# def main():
#     path =os.path.dirname(os.path.abspath(__file__)) ## get the director path of the file
#     filename = "my_file.txt"
#     abs_path= os.path.join(path, filename)
#     print(f"{abs_path} already")

# if __name__ =="__main__":
#     main()