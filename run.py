import locale
import File_processing as file_p

language, encoding = locale.getdefaultlocale()
if language.startswith('zh'):
    path = input('请输入你的bilibili下载目录:\t')
else: 
    path = input('Please enter your Bilibili download directory:\t')
file_p.Get_Filepath(path)
