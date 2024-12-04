import ast

class LeetCodeDebugger(ast.NodeVisitor):
    def __init__(self):
        self.sub_expressions = []
    
    def visit_Import(self, node):
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
    
    def visit_GeneratorExp(self, node):
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
    
    def visit_Call(self, node):
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
    
    def visit_Subscript(self, node):
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
    
    def visit_BoolOp(self, node):
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
        
    def visit_Compare(self, node):  # Handles '==', '<', etc.
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
        
    def visit_BinOp(self, node):  # Handles operations like nums[i] + nums[j]
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
        
    def visit_ListComp(self, node): 
        self.sub_expressions.append(ast.unparse(node))
        self.generic_visit(node)
        
    def visit_If(self, node):
        # Handle 'if' statements by collecting the test condition
        self.sub_expressions.append(ast.unparse(node.test))
        self.generic_visit(node)
    
    def visit_For(self, node):
        # Handle 'for' statements by collecting the loop variable
        self.sub_expressions.append(ast.unparse(node.target))
        self.generic_visit(node)
        
    def get_sub_expressions(self):
        return self.sub_expressions

    def process_line(self, exec_line, prev_variables):
        line = exec_line.strip()

        if line.endswith(':'):
            line = line[:-1]

        for keyword in ['if ', 'while ', 'elif ', 'for ', 'def ']:
            if line.startswith(keyword):
                line = line[len(keyword):]
                break

        tree = ast.parse(line)
        self.visit(tree)

        sub_expressions = sorted(set(self.get_sub_expressions()), key=len)
        results = []

        for expr in sub_expressions:
            try:
                result = eval(expr, {}, prev_variables)
                results.append((expr, result))
            except Exception as e:
                results.append((expr, f""))  # Handle errors gracefully

        return results
    