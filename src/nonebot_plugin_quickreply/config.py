from pydantic import BaseModel


class Config(BaseModel):
    """
      快捷回复插件的配置类
      """
    # 每个用户可创建的总回复数上限，0表示无限制
    quick_reply_max_per_user: int = 0
    # 每个群聊/私聊上下文中的总回复数上限，0表示无限制
    quick_reply_max_per_context: int = 0
