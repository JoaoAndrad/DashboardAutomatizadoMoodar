from typing import List ,Dict ,Any 
import os 
def _preview_with_pandas (path :str ,rows :int =5 )->Dict [str ,Any ]:
    import pandas as pd 
    ext =os .path .splitext (path )[1 ].lower ()
    if ext in ('.xls','.xlsx'):
        df =pd .read_excel (path ,nrows =rows )
    else :
        df =pd .read_csv (path ,nrows =rows )
    cols =list (df .columns .astype (str ))
    rows_data =df .where (pd .notnull (df ),None ).to_dict (orient ='records')
    return {"columns":cols ,"rows":rows_data }
def _preview_with_csv (path :str ,rows :int =5 )->Dict [str ,Any ]:
    import csv 
    with open (path ,'r',encoding ='utf-8',errors ='replace')as f :
        reader =csv .reader (f )
        try :
            header =next (reader )
        except StopIteration :
            return {"columns":[],"rows":[]}
        cols =[h .strip ()for h in header ]
        rows_out :List [Dict [str ,Any ]]=[]
        for i ,r in enumerate (reader ):
            if i >=rows :
                break 
            cells =list (r )+[None ]*max (0 ,len (cols )-len (r ))
            cells =cells [:len (cols )]
            rowd ={cols [j ]:(cells [j ]if cells [j ]!=''else None )for j in range (len (cols ))}
            rows_out .append (rowd )
    return {"columns":cols ,"rows":rows_out }
def parse_preview (path :str ,rows :int =5 )->Dict [str ,Any ]:
    if not os .path .exists (path ):
        raise FileNotFoundError (path )
    try :
        return _preview_with_pandas (path ,rows =rows )
    except Exception :
        return _preview_with_csv (path ,rows =rows )