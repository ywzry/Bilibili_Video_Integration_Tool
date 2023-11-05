import os
import json
import locale
import Fliepr as fv
'''
    ZH_CN:  
            这个脚本将解密视频并整理出视频合集

    EN_US:  
            This script will decrypt the video and organize it into a video collection.

'''
language = [['全部处理完成','地址值不正确','\n-------------------------------------\n文件跳过\n------------------------------------\n',
             '正在准备合并下一个文件.......','无法找到标题文件,自动退出'],
            ['All processing completed','Address value is incorrect',
             '\n-------------------------------------\nfile skip\n------------------------------------\n','Preparing to merge next file...','Unable to find title file, exit automatically']]
lan_g, encoding = locale.getdefaultlocale()
if lan_g.startswith('zh'):
    i=0
else: 
    i=1

def Get_Filepath(get_path):
    '''
        ZH_CN:  
                接收一个参数(项目目录的地址)，然后进行处理
        
        EN_US:  Accept one parameters (the address of the project directory), and then process it.

    '''
    Folder      = Judgment_File(get_path,True)  
    bilibili_root = [item for item in Folder if isinstance(item, str) and item.isdigit()]       
    b_prject      = FP_Combination(get_path,bilibili_root)                  #zh_cn: 获取目录下文件夹，合成下一步路径
                                                                            #en_us: Get the folders under the directory and synthesize the next path

    for b_tmp in b_prject:
        tmp_dlist = Judgment_File(b_tmp,True)
        c_list    = [item for item in tmp_dlist if item.startswith('c_')]   #zh_cn: 查找'c_'开头的文件夹特征（手机版特征）
                                                                            #en_us: Find the characteristics of folders starting with 'c_' (mobile version characteristics)

        if not c_list :
            Win_File(b_tmp)
        else :
            Phone_File(b_tmp,c_list)
    print(language[i][0])
            

def Judgment_File(get_path,c_num):
    '''
        ZH_CN:  
                接收两个参数(目录地址，判断指令)，目录地址会被识别是否存在，判断指令则控制返回目录下的子目录还是返回目录下的文件

        EN_US:  
                Accept two parameters (directory address, judgment command). The directory address will be recognized for existence. 
                The judgment command controls whether to return the subdirectories under the directory or return the files under the directory.
    '''
    if not get_path:
        print(language[i],[1])
        exit()
    else :
        current_directory  = get_path

    #zh_cn: 获取全部文件，并选出筛选文件夹  
    #en_us: Get all files and select filter folders
    files_in_directory     = os.listdir(current_directory)
    files_only = [f for f in files_in_directory if os.path.isfile(os.path.join(current_directory, f))]
    folders = [item for item in files_in_directory if item not in files_only]                                                                                     

    if c_num :
        return  folders
    else:
        return files_only

def FP_Combination(get_path,get_list):
    '''
        ZH_CN:  
                接收两个参数(目录地址，子目录列表)，将目录的地址和地址列表下的子目录合并并返回。

        EN_US:  
                Accept two parameters (directory address, subdirectory list).
                merge the directory address and the subdirectories under the address list, and return.
    '''
    FPC= []
    for i in get_list:
        FPC.append(get_path+'\\'+i)
    return FPC

def Win_File(path):
    '''
        ZH_CN:  
                接收一个参数(目录地址)，这个方法用于查询、生成文件或者合集是否存在，并将文件解密，最后将结果交给filepr.py进行合成处理

        EN_US:  
                Accept one parameter (directory address). 
                This method is used to query whether the file or collection exists and generate it, decrypt the file, and finally pass the result to filepr.py for synthesis processing.
    '''
    tmp_flist = Judgment_File(path,False)           #zh_cn: 获取不包含目录的文件名
                                                    #en_us: Get file name without directory
    if '.videoInfo' in tmp_flist:
        with open(path+'\\.videoInfo','r',encoding='utf-8') as f:
                data    = json.load(f)
        page_data       = data["tabName"]           #zh_cn:  视频标题
                                                    #en_us:  video title
        win_part        = str(data['p'])            #zh_cn:  视频序列号
                                                    #en_us:  Video serial number
        bvid            = str(data['groupId'])      #zh_cn:  bv号码
                                                    #en_us:  bv number
        collection          = str(data['groupTitle'])   
                                                    #zh_cn:  集合名称
                                                    #en_us:  video collection     
        Valid_File_Name = [item for item in tmp_flist  if item[0].isdigit()]  #zh_cn:  获取以数字开头有效文件名
                                                                              #en_us:  Get valid filenames starting with a number
        Xfile_name      = File_Decryption(path,Valid_File_Name)               #zh_cn:  获取解密后的文件名
                                                                              #en_us:  Get the decrypted file name
        special_chars   = "<>:\"/\\|?*"                                       #zh_cn： 创建一个不合法文件名表，根据不同系统自己修改。
                                                                              #en_us:  Create an illegal file name table, you can modify it according to different systems.
        file_name       = page_data+ "_" + bvid 

        if collection in page_data:                     #zh_cn：如果视频标题和视频集合名称一致则说明不是一个集合,传递None使其不创建集合文件夹
                                                    #en_us：If the video title and the video collection name are the same, it indicates that it is not a collection.
            collection      = None
            for char in special_chars:
                file_name   = file_name.replace(char, "_")                    #zh_cn: 替换掉文件名中可能存在的非法目录名
                                                                              #en_us: Replace any illegal directory names that may exist in the file name
        else:
            collection      = collection+'_'+bvid
            file_name       = 'P'+win_part+'_'+page_data
            for char in special_chars:
                file_name   = file_name.replace(char, "_")
                collection  = collection.replace(char, "_")                      #zh_cn: 替换掉可能非法的项目文件夹名称
                                                                             #en_us: Replace potentially illegal project folder names                
        bmp                 = fv.Win_File_Processing(path,Xfile_name,file_name,collection)
        
        if bmp == 1:
            print(language[i][2])
        else:
            print(language[i][3])
        for file_i in Xfile_name:
            d_file = path+'\\'+file_i
            if os.path.exists(d_file):              #zh_cn: 判断解密的文件是否还存在，如果文件存在，那么删除它
                                                    #en_us: Determine whether the decrypted file still exists, if the file exists, then delete it
                os.remove(d_file)
            else:                                   #zh_cn: 如果文件不存在，那么打印一个消息
                                                    #en_us: If the file does not exist, print a message
                print('Decrypted file does not exist')
    else :
        print(language[i][4])
        exit()

def File_Decryption(file_path,file_name):
    '''
        ZH_CN:  
                接收两个参数(文件地址,文件名)这个方法用于解密被加密的视频

        EN_US:  
                Accept two parameters (file address, filename). This method is used to decrypt encrypted videos.
    '''

    for i, file_name_tmp in enumerate(file_name):
        with open(file_path+'\\'+file_name_tmp, 'rb') as f:
            head = f.read(9)        
            rest = f.read()                 
                                            
            if head == b'\x30\x30\x30\x30\x30\x30\x30\x30\x30':     #zh_cn: 检查头部是否是混淆代码
                                                                    #en_us: Check whether the header is obfuscated code
                new_content = rest                                  #zh_cn: 如果是混淆代码，删除它
                                                                    #en_us: If it is obfuscated code, delete it
            else:                      
                new_content = head + rest                           #zh_cn: 如果不是混淆代码，保留原来的内容
                                                                    #en_us: If the code is not obfuscated, keep the original content
            file_name_tmp = 'X'+file_name_tmp                       
            with open(file_path+'\\'+file_name_tmp, 'wb') as f:     #zh_cn: 将新内容写回文件
                                                                    #en_us: Write new content back to file
                f.write(new_content)
            file_name[i] = file_name_tmp
    return file_name

def Phone_File(p_path,c_list):
    '''
        ZH_CN:  
                接收两个参数(目录地址，目录下以'c_'开头的目录列表)，这个方法用于查询、生成文件或者合集是否存在，并将结果交给filepr.py进行合成处理

        EN_US:  
                Accept two parameters (directory address, directory list starting with ‘c_’). 
                This method is used to query whether the file or collection exists and generate it, and then pass the result to filepr.py for synthesis processing.
    '''
    for c in c_list:
        R_num_folder = p_path+'\\'+c            
        with open(R_num_folder+'\\entry.json','r',encoding='utf-8') as f:
            data = json.load(f)
        page_data           = data["page_data"]
        title               = data['title']
        part                = page_data['part'] 
        bvid                = data['bvid']

        num_folder          = [item for item in Judgment_File(R_num_folder,True) if isinstance(item, str) and item.isdigit()]
        for li in num_folder :
            folder_path     = R_num_folder+'\\'+str(li)
        special_chars       = "<>:\"/\\|?*"

        if title in part:
            file_name       = part + "_" + bvid
            collection      = None
            for char in special_chars:
                file_name     = file_name.replace(char, "_")
        else:
            file_name       = part
            collection      = title+'_'+bvid
            for char in special_chars:
                file_name   = file_name.replace(char, "_")
                collection  = collection.replace(char, "_")                  


        bmp                 = fv.P_File_Processing(str(folder_path),str(file_name),collection)

        if bmp == 1:
            print(language[i][2])
        else:
            print(language[i][3])