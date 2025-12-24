from pydantic import Field, BaseModel


class ScopedConfig(BaseModel):
    # 每个用户可创建的总回复数上限，0表示无限制
    max_per_user: int = 0
    # 每个群聊/私聊上下文中的总回复数上限，0表示无限制
    max_per_context: int = 0
    # 是否启用base64图片存储
    enable_base64: bool = True
    # 是否启用权限检查
    enable_permission_check: bool = True


class Config(BaseModel):
    """
    快捷回复插件的配置类
    """

    quickreply: ScopedConfig = Field(default_factory=ScopedConfig)
