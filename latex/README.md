# LaTeX 论文工程

这个目录提供可直接编译的论文 LaTeX 版本。

## 文件

- `main.tex`：论文主文件
- `assets/school_cover.pdf`：由学校封面文档转换得到的封面 PDF
- `build.ps1`：本地编译脚本
- `out/`：编译输出目录

## 编译方式

在 PowerShell 中进入本目录后运行：

```powershell
.\build.ps1
```

若本机已安装 TeX Live 或 MiKTeX，也可以手动运行：

```powershell
xelatex -interaction=nonstopmode -output-directory=out main.tex
xelatex -interaction=nonstopmode -output-directory=out main.tex
```

建议使用 XeLaTeX，以保证中文、数学公式与图片引用正常。

当前模板已经把学校封面作为第 1 页并入，摘要从第 2 页开始。
