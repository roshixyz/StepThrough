let editor;
let currentMark = null;
let lines = []; 
let currentDecoration = [];
let execResults = []; 
let execLine = [];
let prevResults = [];
let subExp = [];
let currentIndex = 0;

function clearHighlight() {
    currentDecoration = editor.deltaDecorations(currentDecoration, []);
}

function highlightLine(lineNumber) {
    clearHighlight();
    const line = lineNumber;  // Monaco lines start from 1 (not 0)
    
    currentDecoration = editor.deltaDecorations(currentDecoration, [
        {
            range: new monaco.Range(line, 1, line, 1), 
            options: {
                isWholeLine: true,
                className: 'highlighted-line'
            }
        }
    ]);
    updateExecResult();
}

function lastHighlight() {
    if (lines.length > 0) {
        currentIndex = lines.length - 1;
        highlightLine(lines[currentIndex]);
    }
}

function resetHighlight() {
    if (lines.length > 0) {
        currentIndex = 0;
        highlightLine(lines[currentIndex]);
    }
}

function highlightNextLine() {
    if (currentIndex < lines.length - 1) {
        currentIndex++;
        highlightLine(lines[currentIndex]);
    }
}

function highlightPreviousLine() {
    if (currentIndex > 0) {
        currentIndex--;
        highlightLine(lines[currentIndex]);
    }
}


function updateExecResult() {

    const tbody = document.querySelector('#exec-table');
        tbody.innerHTML = "";
        Object.entries(execResults[currentIndex]).forEach(([key, value]) => {
            const row = `
            <tr>
                <td class="px-6 py-4 wrap-text text-sm text-gray-500">${key}</td>
                <td class="px-6 py-4 wrap-text text-sm text-gray-500">${value}</td>
            </tr>`;
            tbody.innerHTML += row;
        });

    const subExpTbody = document.querySelector('#sub-exp');
        subExpTbody.innerHTML = "";
        Object.entries(subExp[currentIndex]).forEach(([key, value]) => {
            const row = `
            <tr>
                <td class="px-6 py-4 wrap-text text-sm text-gray-500">${key}</td>
                <td class="px-6 py-4 wrap-text text-sm text-gray-500">${value}</td>
            </tr>`;
            subExpTbody.innerHTML += row;
        });
        Object.entries(execResults[currentIndex]).forEach(([key, value]) => {
            const row = `
            <tr>
                <td class="px-6 py-4 wrap-text text-sm text-gray-500">${key}</td>
                <td class="px-6 py-4 wrap-text text-sm text-gray-500">${value}</td>
            </tr>`;
            subExpTbody.innerHTML += row;
        });
}

require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs' } });

// require(['vs/editor/editor.main'], function() {
//     editor = monaco.editor.create(document.getElementById('editor'), {
//         value: ``,
//         language: 'python',
//         minimap: { enabled: false },
//         scrollbar: {
//             vertical: 'hidden'
//         },
//         lineNumbersMinChars: 2
//     });
//     editor.onDidChangeModelContent(() => {
//         // If the editor content is cleared (empty), clear highlights
//         if (editor.getValue().trim() === "") {
//             clearHighlight();  // Clear highlights when the editor is empty
//         }
//     });

// });
require(['vs/editor/editor.main'], function() {
    editor = monaco.editor.create(document.getElementById('editor'), {
        value: ``,
        language: 'plaintext',
        minimap: { enabled: false },
        scrollbar: {
            vertical: 'hidden'
        },
        lineNumbersMinChars: 1,
        glyphMargin: false,
        fontFamily: 'monospace'
    });

    monaco.editor.defineTheme('customTheme', {
        base: 'vs',
        inherit: false,
        rules: [],
        colors: {
            'editor.foreground': '#000000',
            'editor.background': '#ffffff',
            'editor.lineHighlightBackground': '#ffffff',
            'editorLineNumber.foreground': '#d3d3d3',
            'editorGutter.background': '#f5f5f5'
        }
    });

    monaco.editor.setTheme('customTheme');

    editor.onDidChangeModelContent(() => {
        if (editor.getValue().trim() === "") {
            clearHighlight();
        }
    });
});



async function sendCode() {
    const code = editor.getValue();
    
    const response = await fetch("http://127.0.0.1:8000/send-code", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body: JSON.stringify({ code })
    });

    if (response.ok) {
        const result = await response.json();

        console.log("Response from server:", result);
        if (result.error) {
            alert(result.error);
            return;
        }
        currentIndex = 0;
        
        lines = result["output"].map(output => output.line_no);
        execResults = result["output"].map(output => output.exec_res);
        execLine = result["output"].map(output => output.exec_line);
        prevResults = result["output"].map(output => output.prev_variables);
        subExp = result["output"].map(output => output.sub_exp);        

        // console.log("Response from server:", result);
        if (lines.length > 0) {
            highlightLine(lines[currentIndex]);
        }
    } else {
        alert(response.json());
    } 

}


function switchTab(tabName) {
    // Hide all content
    document.getElementById('variables-content').classList.add('hidden');
    document.getElementById('expressions-content').classList.add('hidden');
    
    // Show selected content
    document.getElementById(`${tabName}-content`).classList.remove('hidden');
    
    // Update tab styles
    document.getElementById('variables-tab').classList.remove('bg-white');
    document.getElementById('expressions-tab').classList.remove('bg-white');
    document.getElementById('variables-tab').classList.add('bg-gray-100');
    document.getElementById('expressions-tab').classList.add('bg-gray-100');
    document.getElementById('variables-tab').classList.add('text-gray-600');
    document.getElementById('expressions-tab').classList.add('text-gray-600');
    
    // Highlight active tab
    document.getElementById(`${tabName}-tab`).classList.remove('bg-gray-100', 'text-gray-600');
    document.getElementById(`${tabName}-tab`).classList.add('bg-white');
  }
  
  // Initialize with Variables tab active
  switchTab('variables');
