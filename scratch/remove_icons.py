import os
import re

src_dir = '/Users/mac/agent/frontend/src'

for root, _, files in os.walk(src_dir):
    for file in files:
        if file.endswith('.jsx'):
            path = os.path.join(root, file)
            with open(path, 'r') as f:
                content = f.read()
            
            # Remove the import line
            content = re.sub(r"import \{.*?\} from 'lucide-react';\n", "", content)
            
            # Remove any self-closing tags for these icons
            # This is slightly dangerous if it catches other components, but the icons are usually
            # simple self-closing tags with size, style, className props.
            # E.g. <Play size={13} />
            # We'll just look for standard lucide-react icon names.
            icons = ["Settings", "FileText", "FlaskConical", "Terminal", "RefreshCw", "AlertCircle", "Newspaper", "Calendar", "BrainCircuit", "ShieldAlert", "Loader", "Database", "Network", "Cpu", "AlertTriangle", "TrendingUp", "TrendingDown", "Zap", "BarChart2", "GitBranch", "Layers", "DollarSign", "PieChart", "History", "Activity", "BookOpen", "Save", "CheckCircle", "Globe", "Play", "DownloadCloud", "XCircle", "Key", "MessageSquare", "Check", "Loader2"]
            
            for icon in icons:
                # Remove self-closing tags like <Icon ... /> or <Icon ...></Icon>
                # Most are self-closing
                content = re.sub(rf"<{icon}\b[^>]*/>", "", content)
                content = re.sub(rf"<{icon}\b[^>]*>.*?</{icon}>", "", content)
                
            with open(path, 'w') as f:
                f.write(content)

print("Icons removed.")
