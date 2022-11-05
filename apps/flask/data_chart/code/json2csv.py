import pandas as pd
import json
import os
import re
import sys
import time
import ray
from os.path import abspath

sys.path.append('../func/')
import utills


col_list = ['msg.CCIP_PTL', 'msg.TTA TESTED.FILENAME', 'msg.TTA TESTED.TTA_TESTVALUE_#04', 'msg.alpha_state.curr-temperature', 'msg.alpha_state.power', 'msg.alpha_state.temperature', 'msg.alpha_temperature', 'msg.base_state.curr-temperature', 'msg.base_state.heaterPower', 'msg.base_state.mode', 'msg.base_state.operation_time', 'msg.base_state.play', 'msg.base_state.power', 'msg.base_state.remained_time', 'msg.base_state.temperature', 'msg.ceramic_dest', 'msg.ceramic_force', 'msg.ceramic_mode', 'msg.ceramic_play', 'msg.ceramic_state.curr-temperature', 'msg.ceramic_state.curr_pinpoint', 'msg.ceramic_state.dest_pinpoint', 'msg.ceramic_state.elapsed_time', 'msg.ceramic_state.force', 'msg.ceramic_state.h-position', 'msg.ceramic_state.mode_index', 'msg.ceramic_state.mode_list', 'msg.ceramic_state.operation_time', 'msg.ceramic_state.play', 'msg.ceramic_state.power', 'msg.ceramic_state.spin-length', 'msg.ceramic_state.state', 'msg.ceramic_state.temperature', 'msg.ceramic_state.v-position', 'msg.ceramic_temperature', 'msg.command_no', 'msg.commander', 'msg.errors', 'msg.ext1_state.curr-temperature', 'msg.ext1_state.curr_pinpoint', 'msg.ext1_state.dest_pinpoint', 'msg.ext1_state.h-position', 'msg.ext1_state.power', 'msg.ext1_state.temperature', 'msg.ext1_temperature', 'msg.ext2_state.curr-temperature', 'msg.ext2_state.temperature', 'msg.ext2_temperature', 'msg.foot_pad.connect', 'msg.foot_pad.force', 'msg.foot_pad.heater', 'msg.foot_pad.mode', 'msg.foot_pad.on', 'msg.foot_pad.play', 'msg.foot_pad_force', 'msg.foot_pad_on', 'msg.information.firmware_ver', 'msg.information.iotm_fw_ver', 'msg.information.machine_fw_ver', 'msg.information.machine_no', 'msg.information.serial_no', 'msg.mode', 'msg.mode_index', 'msg.mode_list', 'msg.multi_pad.connect', 'msg.multi_pad.force', 'msg.multi_pad.heater', 'msg.multi_pad.mode', 'msg.multi_pad.on', 'msg.multi_pad.play', 'msg.multi_pad_force', 'msg.multi_probe.connect', 'msg.multi_probe.force', 'msg.multi_probe.heater', 'msg.multi_probe.mode', 'msg.multi_probe.on', 'msg.multi_probe.play', 'msg.multi_probe.temperature', 'msg.multi_probe_force', 'msg.multi_probe_mode', 'msg.multi_probe_on', 'msg.music.bluetooth_name', 'msg.music.music_no', 'msg.music.play', 'msg.music.source', 'msg.music.sourcelist', 'msg.music.voice_guidance', 'msg.music.volume', 'msg.music_play', 'msg.music_select', 'msg.music_source', 'msg.music_volume', 'msg.play', 'msg.power', 'msg.rect_pad.connect', 'msg.rect_pad.force', 'msg.rect_pad.heater', 'msg.rect_pad.mode', 'msg.rect_pad.on', 'msg.rect_pad_force', 'msg.rect_pad_on', 'msg.refresh', 'msg.replay', 'msg.reply.activated', 'msg.reply.command_no', 'msg.reply.commander', 'msg.reply.power', 'msg.sender', 'msg.set_active_commander', 'msg.side_pad.connect', 'msg.side_pad.force', 'msg.side_pad.heater', 'msg.side_pad.mode', 'msg.side_pad.on', 'msg.side_pad_force', 'msg.side_pad_mode', 'msg.stomach_force', 'msg.stomach_mode', 'msg.stomach_pad.connect', 'msg.stomach_pad.curr-temperature', 'msg.stomach_pad.dest_pinpoint', 'msg.stomach_pad.force', 'msg.stomach_pad.heater', 'msg.stomach_pad.mode', 'msg.stomach_pad.on', 'msg.stomach_pad.play', 'msg.stomach_pad.power', 'msg.stomach_pad.temperature', 'msg.stomach_pad_force', 'msg.stomach_pad_heater_on', 'msg.stomach_pad_mode', 'msg.stomach_pad_on', 'msg.stomach_play', 'msg.stomach_temperature', 'msg.sub_force', 'msg.sub_mode', 'msg.sub_play', 'msg.sub_state.curr-temperature', 'msg.sub_state.dest_pinpoint', 'msg.sub_state.force', 'msg.sub_state.mode', 'msg.sub_state.play', 'msg.sub_state.power', 'msg.sub_state.state', 'msg.sub_state.temperature', 'msg.sub_temperature', 'msg.temperature', 'msg.timesync', 'msg.voice_guidance', 'regdate', 'regdate-display', 's', 'topic']

@ray.remote
def json2csv(json_file, csv_path, out_path, rmfile):
    try:
        # json 파일 읽은 후 데이터를 DataFrame으로 변환
        with open(json_file, 'r') as fname:  
            d = fname.readline()
            data = json.loads(d)
        df = pd.json_normalize(data)
    except Exception as e:
        print(e)
        print(json_file)
        return 0
    
    for col in set(col_list) - set(list(df.columns)):
        df[col] = None
    df = df[col_list]
        
    file_name = json_file.split('/')[-1].split('.')[0]
    try:
        if not os.path.isdir(out_path):
            os.makedirs(out_path)
    except:
        pass
    # DataFrame 데이터 CSV파일로 저장
    df.to_csv(out_path + '/' + file_name + '.csv', index=False)
        
    if rmfile == 'rm':
        os.remove(csv_file)
    
    return len(df), json_file


processed_list = []
try:
    import processed_list
    processed_list = processed_list.processed_list
except:
    pass

if csv_path[-1] == '/':
    csv_path = csv_path[:-1]
if out_path[-1] == '/':
    out_path = out_path[:-1]

print ("json Dir location = ", csv_path)
json_list = []

print('json 파일 목록 불러오는 중..')
utills.recursive_search_dir(csv_path, json_list, 'json')
json_list.sort()
i = 0
while True:
    if i >= len(json_list):
        break
    if json_list[i] in processed_list:
        del json_list[i]
    else:
        i+=1

print('\n처리할 json파일 수 : {}'.format(len(json_list)))

proc_start_time = time.time()

# ray 멀티프로세싱 초기화
try:
    if pn <= 0:
        ray.init()
    else:    
        ray.init(num_cpus=pn)
except:
    ray.shutdown()
    if pn <= 0:
        ray.init()
    else:    
        ray.init(num_cpus=pn)

cnt=1
t_cnt = len(json_list)
print('\njson -> csv 변환 시작')
obj_id_list = []
for _file in json_list:
    obj_id_list.append(json2csv.remote(_file, csv_path, out_path, rmfile))

processed_lines=0
while len(obj_id_list):
    utills.printProgressBar(cnt, t_cnt)
    done, obj_id_list = ray.wait(obj_id_list)
    lines, processed_file = ray.get(done[0])
    processed_lines += lines
    processed_list.append(processed_file)
    with open('processed_list.py', 'w') as fw:
        fw.write('processed_list=%s\n' %processed_list)
    cnt+=1
print("\n처리 완료\n처리된 데이터 라인 수 : {}".format(processed_lines))
print("출력 파일 경로 : {}".format(abspath(out_path)))
print('total running time : {:.2f} sec'.format(time.time()-proc_start_time))

ray.shutdown()