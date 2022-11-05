#-*-coding:utf-8-*-
from flask import Flask, render_template, request, url_for
from IPython.display import Image, display, clear_output
import sys

##
## Flask 객체를 app에 할당
app = Flask(__name__, static_url_path='/static')

## GET 방식으로 값을 전달받음. 
## 아무 값도 넘겨받지 않는 경우도 있으므로 비어 있는 url도 함께 mapping해주는 것이 필요함
## app 객체를 이용해 라우팅 경로를 설정

@app.route('/')
def home(result=None):
    return render_template('home.html')

@app.route('/preproc', methods=['POST', 'GET'])
def preproc(result=None):
    if request.method == 'POST':
        pass
    elif request.method == 'GET':
        temp1 = request.args.get('ip')
        temp2 = request.args.get('port')
        temp3 = request.args.get('field')

        print(request.args)
        return render_template('preprocessing.html')

    return render_template('preprocessing.html')

@app.route('/preproc_args', methods=['POST', 'GET'])
def preproc_args(result=None):
    if request.method == 'POST':
        pass
    elif request.method == 'GET':
        temp1 = request.args.get('ip')
        temp2 = request.args.get('port')
        temp3 = request.args.get('field')

        print(request.args)
        return render_template('preproc_args.html')

    return render_template('preproc_args.html')


## /txt 로 접근하면 다음 부분이 수행됨 
@app.route('/log')
def read_txt():
    f = open('./static/run_log.log', 'r')
    ## 단 리턴되는 값이 list형태의 타입일 경우 문제가 발생할 수 있음.
    ## 또한 \n이 아니라 </br>으로 처리해야 이해함
    ## 즉 파일을 읽더라도 이 파일을 담을 html template를 만들어두고, render_template 를 사용하는 것이 더 좋음
    return "</br>".join(f.readlines())


@app.route('/img')
def print_img():
    return render_template('ShowImg.html')


@app.route('/argument')
def args(result=None):
  return render_template('argument.html')


@app.route('/chart')
def chart(result=None):
  return render_template('chart.html')


@app.route('/chart_form', methods=['POST', 'GET'])
def chart_form(result=None):
    sys.path.append('./code/')
    import chart
    import utils
    if request.method == 'POST':
        pass
    elif request.method == 'GET':
        csv_path = request.args.get('csv_path')
        csv_file = request.args.get('csv_file')
        time_field = request.args.get('time_field')
        to_plot_field = request.args.get('to_plot_field')
        start_date = request.args.get('start_date')
        start_time = request.args.get('start_time')
        end_date = request.args.get('end_date')
        end_time = request.args.get('end_time')
        if csv_file == None:
            csv_list = []
            err = 0
            try:
                utils.recursive_search_dir(csv_path, csv_list)
            except:
                err = 1
            if err == 1: return render_template('chart_form.html')
            else: return render_template('chart_form.html', data0 = csv_path, data1 = csv_list)
        elif time_field == None or to_plot_field == None:
            try:
                import pandas as pd
                # /home/keti/data/csv_split_by_id/1c9dc244e5bc.csv
                df = pd.read_csv(csv_file, low_memory=False)
                df_len = len(df)
                notnan = df.notna().sum()
                notnancols = []
                for col in df.columns:
                    if notnan[col] > 0:
                        notnancols.append(col)
                cols = notnancols
        
                # df 필드 중 값이 object일 경우 tag로 빼놓기
                df_field_type_dict = df.dtypes.to_dict()
                _tag = []
                for d in cols:
                    if df_field_type_dict[d] == 'object':
                        _tag.append(d)
                    else:
                        continue
        
                # df 필드 중 값이 string일 경우 tag_str로 빼놓기
                _tag_str = []
                for d in cols:
                    if df_field_type_dict[d] == 'unicode':
                        _tag_str.append(d)
                    else:
                        continue
        
                _numeric = list(set(notnancols) - set(_tag) - set(_tag_str)) 
                print(_numeric)
                return render_template('chart_form.html', data0 = csv_path, data1 = csv_file, data2 = _numeric)
            except Exception as e:
                print(csv_path)
                print(e)
        elif start_date == None or start_time == None or end_date == None or end_time == None:
            try:
              import pandas as pd
              import datetime
              # /home/keti/data/csv_split_by_id/1c9dc244e5bc.csv
              print(to_plot_field)
              cols = list(to_plot_field.split('|')) + [time_field]
              print(cols)
              new_cols = []
              for col in cols:
                  if col not in new_cols:
                      new_cols.append(col)
              print(new_cols)
              df = pd.read_csv(csv_file, low_memory=False, usecols=new_cols)
              min_time = str(datetime.datetime.fromtimestamp(int(df[time_field].min())/1000.0))
              start_date = min_time[0:10]
              start_time = min_time[11:16]
              max_time = str(datetime.datetime.fromtimestamp(int(df[time_field].max())/1000.0))
              end_date = max_time[0:10]
              end_time = max_time[11:16]
              new_cols = "|".join(new_cols)
              print(new_cols)
              return render_template('chart_form.html', data0 = csv_path, data1 = csv_file, data2 = new_cols, data3 = time_field, data4 = start_date, data5 = start_time, data6=end_date, data7=end_time)
            except Exception as e:
                print(csv_path)
                print(e)
        else:
            import pandas as pd
            import datetime
      
            new_cols = list(to_plot_field.split('|'))
            start_date_time = start_date + ' ' + start_time + ":00"
            end_date_time = end_date + ' ' + end_time + ":00"
            print(start_date_time)
            print(end_date_time)
            df = pd.read_csv(csv_file, low_memory=False, usecols=new_cols)
            new_cols.remove(time_field)
            png_path = chart.draw_chart(df, new_cols, time_field, start_date_time, end_date_time)
            new_cols.append(time_field)
            df = pd.read_csv(csv_file, low_memory=False, usecols=new_cols)
            min_time = str(datetime.datetime.fromtimestamp(int(df[time_field].min())/1000.0))
            start_date = min_time[0:10]
            start_time = min_time[11:16]
            max_time = str(datetime.datetime.fromtimestamp(int(df[time_field].max())/1000.0))
            end_date = max_time[0:10]
            end_time = max_time[11:16]
            new_cols = '|'.join(new_cols)
            return render_template('chart_form.html', data0 = csv_path, data1 = csv_file, data2 = new_cols, data3 = time_field, data4 = start_date, data5 = start_time, data6=end_date, data7=end_time, data8 = png_path)

    return render_template('chart_form.html', data1 = "", data2 = [])

@app.route('/charting')
def charting():
    return render_template('charting.html', args = False)

if __name__ == '__main__':
    # threaded=True 로 넘기면 multiple plot이 가능해짐
    app.run(host='0.0.0.0', port=9999, debug=True, threaded=True)
