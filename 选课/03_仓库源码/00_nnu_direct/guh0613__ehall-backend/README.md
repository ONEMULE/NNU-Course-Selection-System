# ehall-backend
ehall-backend是一个纯api式的服务端，使用Flask框架运行。该服务端可与特定后端交互，整理相关数据。

## 声明
本项目仅供学习用途，本项目的开发者不对任何由于使用本项目而产生的直接或间接后果负责。使用者在使用本项目时，应确保交互后端由自己运行或授权，自行承担任何可能的法律风险。

## API端点
详见[API文档](docs/api.md)

## 开发
环境要求：Python 3.10+

### 1. 安装依赖

使用支持[PEP 621](https://peps.python.org/pep-0621/)的工具安装依赖，如`poetry`或`pdm`，推荐使用`pdm`。
```shell
pdm init
pdm install
```

### 2. 运行
```shell
flask run
```
仅供开发使用，生产环境请使用WSGI服务器。
