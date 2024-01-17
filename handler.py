
from functools import wraps
from collections import defaultdict
import inspect
import re
from typing import Any, Callable

from box import Box
from dash_extensions.enrich import Input, Output, State
import dash

class Handlers:
    @staticmethod
    def _as_list(item):
        if item is None:
            return []
        if isinstance(item, tuple):
            return list(item)
        if isinstance(item, list):
            return item
        return [item]

    @staticmethod
    def _callback_inputs(*args: Any):
        outputs = []
        inputs = []
        states = []
        for arg in args:
            elements = Handlers._as_list(arg)
            for element in elements:
                if isinstance(element, Output):
                    outputs.append(element)
                elif isinstance(element, Input):
                    inputs.append(element)
                elif isinstance(element, State):
                    states.append(element)

        return outputs, inputs, states

    @staticmethod
    def callback(*args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        outputs, inputs, states = Handlers._callback_inputs(*args)
        def decorator(func: Callable[[Any], Any]):
            @dash.callback(outputs, inputs, states, **kwargs)
            @wraps(func)
            def wrapper(*args: Any):
                i = {
                    element.component_id : { element.component_property: value }
                    for element, value in zip(inputs + states, args)
                }
                o = {
                    element.component_id : { element.component_property: dash.no_update }
                    for element in outputs
                }
                def inner_wrapper(f):
                    def change_output(*args):
                        box = f(*args)
                        return [box[o.component_id][o.component_property] for o in outputs]
                    return change_output
                
                f = inner_wrapper(func)
                return f(Box(i), Box(o))

        return decorator

    @staticmethod
    def get_inputs(*args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        outputs, inputs, states = Handlers._callback_inputs(*args)
        input_dct = [{'component_id': o.component_id, 'component_property': o.component_property, 'var_name': None} for o in inputs + states]
        output_dct = [{'component_id': o.component_id, 'component_property': o.component_property, 'var_name': None} for o in outputs]
        
        fake_args = range(len(input_dct))
        def wrapper(func):
            def replace_parameters(source):
                start = source.index(func.__name__) 
                end = source.find(":")
                source = source[:start]  + f"{func.__name__}(inputs, outputs)" + source[end:]
                return source

            def replace_variable(source, var_info):
                id, prop, var_name = var_info['component_id'], var_info['component_property'], var_info['var_name']
                if var_name:
                    source = re.sub(rf"\b{var_name}\b", f"inputs.{id}.{prop}", source)
                return source
            
            def for_each_return_statement(source):
                def is_variable(x):
                    bad = "'\"[](){}"
                    bad2 = ['True', 'False', 'None'] 
                    not_var = any(c in x for c in bad) or any(w == x for w in bad2)
                    return not not_var
        
                def get_output_dct(ret):
                    import copy
                    output_d = copy.deepcopy(output_dct)
                    ret = ret.strip(" ()[]")
                    ret = ret.replace(",", "")
                    for i, r in enumerate(ret.split()):
                        o = next(x for x in output_d if x['component_id'] == outputs[i].component_id)
                        o['var_name'] = r
                    return output_d
                
                def add_to_var_output_mapping(var_output_mapping, output_d):
                    for var in output_d:
                        var_name = var['var_name']
                        if is_variable(var_name):
                            id = var['component_id']
                            prop = var['component_property']
                            var_output_mapping[var_name].append(f"{id}.{prop}")

                def replace_return_with_assignment(source, ret, output_d):
                    new1 = [ f"outputs.{output['component_id']}.{output['component_property']}" for output in output_d ]
                    new2 = [ f"{output['var_name']}" for output in output_d ]

                    new = ", ".join(new1) + " = " + ", ".join(new2)
                    source = re.sub(f"return.*{ret}", new, source)
                    return source

                def replace_output_variable(source, var):
                    old_name = var['var_name']
                    new_name = f"outputs.{var['component_id']}.{var['component_property']}"
                    source = re.sub(rf"\b{old_name}\b", new_name, source)
                    return source

                source = source.replace("\\\n", "")
                m = re.findall(r"return(.*)", source)
                var_output_mapping = defaultdict(list)
                ret_mapping = {}

                # create data structures
                for ret in m: 
                    output_d = get_output_dct(ret)
                    ret_mapping[ret] = output_d
                    add_to_var_output_mapping(var_output_mapping, output_d)

                # replace return statements
                for ret in ret_mapping:
                    output_d = ret_mapping[ret]
                    source = replace_return_with_assignment(source, ret, output_d)

                # replace variables
                for ret in ret_mapping:
                    output_d = ret_mapping[ret]
                    vars = list(filter(lambda x: x['var_name'], output_d))
                    for var in vars:
                        var_name = var['var_name']
                        if var_name and len(var_output_mapping[var_name]) == 1:
                            source = replace_output_variable(source, var)

                return source

            def for_each_assignment_statement(source):
                def get_assignments(source):
                    assign = []
                    return assign

                def remove_unnecessary(assign):
                    def is_output(x):
                        return any(x == f"outputs.{o['component_id']}.{o['component_property']}" for o in output_dct)
                    return assign
                
                def convert(source, assign, assign2):
                    for a in assign:
                        pass

                assign = get_assignments(source)
                assign2 = remove_unnecessary(assign)
                convert(source, assign, assign2)


            def inner_wrapper(*inner_args, **inner_kwargs):
                func_source = inspect.getsource(func)
                # update function definition
                func_source = replace_parameters(func_source)

                # update inputs
                args_name = inspect.getargspec(func)[0]
                for name, input in zip(args_name, input_dct):
                    input.update({'var_name': name})
                for i in input_dct: 
                    func_source = replace_variable(func_source, i)

                # update outputs
                func_source = for_each_return_statement(func_source)
                print(func_source)
                func_source = for_each_assignment_statement(func_source)

                return func(*inner_args, **inner_kwargs)
            
            inner_wrapper(*fake_args)
            return inner_wrapper
        return wrapper
    
    
    




