<div align="center">
    <a href="https://v2.nonebot.dev/store">
    <img src="https://raw.githubusercontent.com/fllesser/nonebot-plugin-template/refs/heads/resource/.docs/NoneBotPlugin.svg" width="310" alt="logo"></a>

## ✨ 快捷回复 ✨
[![LICENSE](https://img.shields.io/github/license/FlanChanXwO/nonebot-plugin-quickreply.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-quickreply.svg)](https://pypi.python.org/pypi/nonebot-plugin-quickreply)
[![python](https://img.shields.io/badge/python-3.10|3.11|3.12|3.13-blue.svg)](https://www.python.org)
[![uv](https://img.shields.io/badge/package%20manager-uv-black?style=flat-square&logo=uv)](https://github.com/astral-sh/uv)
<br/>
[![ruff](https://img.shields.io/badge/code%20style-ruff-black?style=flat-square&logo=ruff)](https://github.com/astral-sh/ruff)
[![pre-commit](https://results.pre-commit.ci/badge/github/FlanChanXwO/nonebot-plugin-quickreply/master.svg)](https://results.pre-commit.ci/latest/github/FlanChanXwO/nonebot-plugin-quickreply/master)

</div>

## 📖 介绍

一个功能强大的快捷回复插件，支持分群/私聊、配置化限制最大快捷回复数量。

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-quickreply --upgrade
使用 **pypi** 源安装

    nb plugin install nonebot-plugin-quickreply --upgrade -i "https://pypi.org/simple"
使用**清华源**安装

    nb plugin install nonebot-plugin-quickreply --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"


</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details open>
<summary>uv</summary>

    uv add nonebot-plugin-quickreply
安装仓库 main 分支

    uv add git+https://github.com/FlanChanXwO/nonebot-plugin-quickreply@main
</details>

<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-quickreply
安装仓库 main 分支

    pdm add git+https://github.com/FlanChanXwO/nonebot-plugin-quickreply@main
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-quickreply
安装仓库 main 分支

    poetry add git+https://github.com/FlanChanXwO/nonebot-plugin-quickreply@main
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_quick_reply"]

</details>

<details>
<summary>使用 nbr 安装(使用 uv 管理依赖可用)</summary>

[nbr](https://github.com/fllesser/nbr) 是一个基于 uv 的 nb-cli，可以方便地管理 nonebot2

    nbr plugin install nonebot-plugin-quickreply
使用 **pypi** 源安装

    nbr plugin install nonebot-plugin-quickreply -i "https://pypi.org/simple"
使用**清华源**安装

    nbr plugin install nonebot-plugin-quickreply -i "https://pypi.tuna.tsinghua.edu.cn/simple"

</details>


## ⚙️ 配置

在 nonebot2 项目的`.env`或`.env.prod`文件中添加下表中的配置

|              配置项              | 必填 |  默认值   | 说明                                                  |
|:-----------------------------:| :---: |:------:|:----------------------------------------------------|
|  `QUICKREPLY__MAX_PER_USER`   | 否 |  `0`   | 每个用户可创建的总回复数上限，`0`表示无限制                             |
| `QUICKREPLY__MAX_PER_CONTEXT` | 否 |  `0`   | 每个群聊/私聊上下文中的总回复数上限，`0`表示无限制                         |
|  `QUICKREPLY__ENABLE_BASE64`  | 否 | `True` | 是否将图片消息转化为base64存储，有的图片消息可能会过期可以启用该项，但是可能会造成数据库内容冗余 |
| `QUICKREPLY__ENABLE_PERMISSION_CHECK` | 否 |  `True`  | 是否启用权限检查,启用该选项后，超管/管理创建或覆盖的回复不可被普通成员覆盖              |
## 🎉 使用
### 指令表
根据指令作用范围分为 **上下文相关** 和 **全局** 两类。

#### 上下文相关指令 (仅在当前群聊/私聊生效)
| 指令 | 权限 | 需要@ | 范围 | 说明 |
| :---: | :---: | :---: | :---: | :--- |
| `/设置回复 <关键词> <内容>` | 所有用户 | 否 | 群聊/私聊 | 添加或覆盖一条回复 (别名: `/回复设置`) |
| `/删除回复 <关键词>` | 创建者 | 否 | 群聊/私聊 | 删除自己创建的回复 (别名: `/回复删除`, `/清除回复`) |
| `/回复列表` | 所有用户 | 否 | 群聊/私聊 | 查看当前上下文的所有回复 (别名: `/本群回复`) |
| `/我在本会话的回复列表` | 所有用户 | 否 | 群聊/私聊 | 查看自己在本会话创建的回复 (别名: `/我在本群的回复列表`) |
| `/清空我在本会话的回复` | 创建者 | 否 | 群聊/私聊 | 删除自己在本会话创建的所有回复 (别名: `/清空我在本群的回复`) |
| `/清空本会话回复` | 群管/超管 | 否 | 群聊/私聊 | 清空本会话的所有快捷回复 (别名: `/清空本群回复`) |

#### 全局指令 (影响您所有的回复)
| 指令 | 权限 | 需要@ | 范围 | 说明 |
| :---: | :---: | :---: | :---: | :--- |
| `/我的回复列表` | 所有用户 | 否 | 全局 | 查看自己创建的所有回复 (别名: `/我的快捷回复`) |
| `/清空我的回复` | 所有用户 | 否 | 全局 | 删除自己创建的所有回复 (别名: `/清空我的快捷回复`) |
| `/清空用户回复 <@用户或QQ>` | 超级用户 | 是 | 全局 | 删除指定用户创建的所有回复 (别名: `/清除用户回复`) |

### 🎨 效果图
![img.png](assets/img.png)
![img_1.png](assets/img_1.png)
![img_2.png](assets/img_2.png)
![img_3.png](assets/img_3.png)
![img_4.png](assets/img_4.png)
![img_5.png](assets/img_5.png)
![img_6.png](assets/img_6.png)
![img_7.png](assets/img_7.png)