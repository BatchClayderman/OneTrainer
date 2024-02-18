import os
from sys import exit
os.chdir(os.path.abspath(os.path.dirname(__file__)))
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EOF = (-1)
folderPath = "train"
exts = [".png"]


def generate_txt_files(folder_path, encoding = "utf-8") -> tuple:
	success_cnt = 0
	total_cnt = 0
	for root, dirs, files in os.walk(folder_path):
		for fl in files:
			if os.path.splitext(fl)[1].lower() in exts:
				total_cnt += 1
				file_name = os.path.splitext(fl)[0]
				txt_file_name = file_name + ".txt"
				txt_file_path = os.path.join(root, txt_file_name)
				try:
					with open(txt_file_path, "w", encoding = encoding) as txt_file:
						txt_file.write("a photo of {0}".format(file_name.split("_")[0]))
					success_cnt += 1
				except:
					pass
	return (success_cnt, total_cnt)

def main() -> int:
	success_count, total_count = generate_txt_files(folderPath)
	return EXIT_SUCCESS if success_count == total_count else EXIT_FAILURE



if __name__ == "__main__":
	exit(main())