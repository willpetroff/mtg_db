import json
import random
import string
import traceback

from datetime import date
from math import ceil
from sqlalchemy.sql import func


class DotDict:
    def __init__(self, **attrs):
        self.__dict__.update(attrs)

    # def __getattr__(self, name):
    #     if name in self:
    #         return self[name]
    #     return super().__getattr__(name)
    #     return getattr(self, name, None)

    # def __setattr__(self, name, value):
    #     if name in self.keys():
    #         self[name] = value
    #     return super().__setattr__(name, value)


def paginate(query, current_page, per_page=30, stretch=2, group_by=False):
    record_count = row_count(query, group_by)
    max_page = ceil(record_count / per_page)
    if current_page > 1:
        query = query.offset(per_page * (current_page - 1))
    records = query.limit(per_page).all()
    if records:
        low_page = current_page - stretch
        if low_page < 1:
            low_page = 1
        high_page = current_page + stretch
        if high_page > max_page:
            high_page = max_page
    else:
        low_page = 0
        high_page = 0
    page_list = [page for page in range(low_page, high_page+1)]
    if page_list[0] > 1:
        no_first = True
    else:
        no_first = False
    if page_list[len(page_list)-1] < max_page:
        no_max = True
    else:
        no_max = False
    pagination = {
        "RecordCount": record_count,
        "CurrentPage": current_page,
        "MaxPage": max_page,
        "RecordsPerPage": per_page,
        "PageList": page_list,
        "NoFirst": no_first,
        "NoMax": no_max
    }
    return records, pagination


def pretty_exception(exc):
    if exc:
        exc_type, exc_value, exc_traceback = exc
        stack_list = []
        stack_default = [{
            "filename": exc_traceback.tb_frame.f_code.co_filename,
            "lineno": exc_traceback.tb_lineno
        }]
        for stack_item in traceback.walk_tb(exc[2]):
            if '/lib/' not in stack_item[0].f_code.co_filename:
                filename = stack_item[0].f_code.co_filename
                lineno = stack_item[1]
                stack_list.append({
                    "filename": filename,
                    "lineno": lineno
                })
        exception_details = {
            "stack_list": stack_list if stack_list else stack_default,
            "name": exc_traceback.tb_frame.f_code.co_name,
            "type": exc_type.__name__,
            "message": getattr(exc_value, "message", str(exc_value))
        }
        return json.dumps(exception_details)
    return None


def row_count(q, group_by):
    if not group_by:
        count_q = q.statement.with_only_columns([func.count()]).order_by(None)
        count = q.session.execute(count_q).scalar()
    else:
        count = q.count()
    return count
