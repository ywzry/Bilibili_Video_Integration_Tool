import subprocess
import os
import locale
'''
    ZH_CN: 
            这个脚本获取处理后的数据并进行合成

    EN_US:  
            This script obtains the processed data and performs synthesis.
'''

language =[['开始自 ','视频音频合成完成','音频文件不存在'],['Start from ','Video and audio synthesis completed','Audio file does not exist']]
lan_g, encoding = locale.getdefaultlocale()
if lan_g.startswith('zh'):
    i=0
else: 
    i=1

def Win_File_Processing(path,oldname,filename,collection):
    '''
        ZH_CN:  
                接收四个参数(地址，旧的文件名，合成文件名，集合名称)，根据参数进行合成

        EN_US:  
                Accept four parameters (address, old filename, composite filename, collection name), and perform synthesis based on these parameters.
    '''
    out_PATH            = '.\\win_bilibili\\'

    if not collection:
        os.makedirs(out_PATH,exist_ok=True)
    else:
        out_PATH        = out_PATH+collection
        os.makedirs(out_PATH,exist_ok=True)
        out_PATH        =out_PATH+'\\'

    if os.path.exists(out_PATH+filename+'.MP4'):
        return 1
    else:
        with open(out_PATH+'win_temp.log', 'a') as f:
            f.write(language[i][0] + path )
        oldnamev        = str(oldname[0])
        oldnamem        = str(oldname[1])

    if os.path.exists(path+'\\'+oldnamev) and os.path.exists(path+'\\'+oldnamem):
        subprocess.check_output(['ffmpeg', '-i', path+'\\'+oldnamev, '-i', path+'\\'+oldnamem, '-codec', 'copy', out_PATH+filename+'.MP4'])
        print(language[i][1])
    else: 
        if not oldnamev :
            temp_file   = oldnamev
        else:
            temp_file   = oldnamem
        subprocess.check_output(['ffmpeg', '-i', path+'\\'+temp_file, '-codec', 'copy', out_PATH+filename+'.MP4'])
        print(language[i][2])
        print("OK")

def P_File_Processing(path,filename,collection):
    '''
        ZH_CN:  
                接收三个参数(地址，合成文件名，集合名称)，然后进行合成

        EN_US:  
                Accept three parameters (address, composite filename, collection name), and then perform synthesis.
    '''
    out_PATH            = '.\\D_bilibili\\'
    if not collection:
        os.makedirs(out_PATH,exist_ok=True)
    else:
        out_PATH        = out_PATH+collection
        os.makedirs(out_PATH,exist_ok=True)
        out_PATH        = out_PATH+'\\'

    if os.path.exists(out_PATH+filename+'.MP4'):
       return 1
    else:
        with open(out_PATH+'temp.log', 'a') as f:
            f.write(language[i][0] + path)

    if os.path.exists(path+'\\audio.m4s'):
        subprocess.check_output(['ffmpeg', '-i', path+'\\video.m4s', '-i', path+'\\audio.m4s', '-codec', 'copy', out_PATH+filename+'.MP4'])
        print(language[i][1])
    else:
        subprocess.check_output(['ffmpeg', '-i', path+'\\video.m4s', '-codec', 'copy', out_PATH+filename+'.MP4'])
        print(language[i][2])
        print("OK")




