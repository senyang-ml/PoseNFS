# modified from https://github.com/tonylins/pytorch-mobilenet-v2/blob/master/MobileNetV2.py

import torch
import torch.nn as nn
import math
import logging
import os
logger = logging.getLogger(__name__)

def conv_bn(inp, oup, stride):
    return nn.Sequential(
        nn.Conv2d(inp, oup, 3, stride, 1, bias=False),
        nn.BatchNorm2d(oup),
        nn.ReLU6(inplace=True)
    )


def conv_1x1_bn(inp, oup):
    return nn.Sequential(
        nn.Conv2d(inp, oup, 1, 1, 0, bias=False),
        nn.BatchNorm2d(oup),
        nn.ReLU6(inplace=True)
    )


class InvertedResidual(nn.Module):
    def __init__(self, inp, oup, stride, expand_ratio):
        super(InvertedResidual, self).__init__()
        self.stride = stride
        assert stride in [1, 2]

        hidden_dim = round(inp * expand_ratio)
        self.use_res_connect = self.stride == 1 and inp == oup

        if expand_ratio == 1:
            self.conv = nn.Sequential(
                # dw
                nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # pw-linear
                nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup),
            )
        else:
            self.conv = nn.Sequential(
                # pw
                nn.Conv2d(inp, hidden_dim, 1, 1, 0, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # dw
                nn.Conv2d(hidden_dim, hidden_dim, 3, stride, 1, groups=hidden_dim, bias=False),
                nn.BatchNorm2d(hidden_dim),
                nn.ReLU6(inplace=True),
                # pw-linear
                nn.Conv2d(hidden_dim, oup, 1, 1, 0, bias=False),
                nn.BatchNorm2d(oup),
            )

    def forward(self, x):
        if self.use_res_connect:
            return x + self.conv(x)
        else:
            return self.conv(x)


class MobileNetV2(nn.Module):
    def __init__(self,feature_num=4,frozen_mobilenet=False, width_mult=1.,**kwargs):
        super(MobileNetV2, self).__init__()
        block = InvertedResidual
        input_channel = 32
        last_channel = 1280
        interverted_residual_setting = [
            # t, c, n, s
            [1, 16, 1, 1],
            [6, 24, 2, 2],
            [6, 32, 3, 2],
            [6, 64, 4, 2],
            [6, 96, 3, 1],
            [6, 160, 3, 2],
            [6, 320, 1, 1],
        ]
        
        # building first layer
        assert feature_num == 4
        self.feature_num = feature_num
        self.frozen_mobilenet = frozen_mobilenet
        input_channel = int(input_channel * width_mult)
        self.last_channel = int(last_channel * width_mult) if width_mult > 1.0 else last_channel


        #self.features0 = [conv_bn(3, input_channel, 2)]
        self.features=nn.ModuleList()
        self.features.append(conv_bn(3, input_channel, 2))

        # building inverted residual blocks
        for t, c, n, s in interverted_residual_setting:

            output_channel = int(c * width_mult)
            for i in range(n):
                if i == 0:
                    self.features.append(block(input_channel, output_channel, s, expand_ratio=t))
                else:
                    self.features.append(block(input_channel, output_channel, 1, expand_ratio=t))
                input_channel = output_channel

        if frozen_mobilenet:
            for param in self.parameters():
                param.requires_grad = False

    def forward(self, x):

        # layer nums in each scale = [1+1,2,3,4,3,3]  for scale [1/2,1/4,1/8,1/16,1/32]
        x = self. features[0](x) 
        x = self. features[1](x) # 1/2

        x = self. features[2](x) 
        x = self. features[3](x) # 1/4

        f_4 = x.clone()
        x = self. features[4](x)
        x = self. features[5](x)
        x = self. features[6](x) # 1/8
        f_8 = x.clone()

        x = self. features[7](x)
        x = self. features[8](x)
        x = self. features[9](x)
        x = self. features[10](x) #1/16
        

        x = self. features[11](x)
        x = self. features[12](x)
        x = self. features[13](x) #1/16
        f_16 = x.clone()

        x = self. features[14](x)
        x = self. features[15](x)
        f_32 = self. features[16](x) # 1/32
        
        return f_4,f_8,f_16,f_32

    def init_weights(self, use_pretrained=True, pretrained=''):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
                if m.bias is not None:
                    m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.Linear):
                n = m.weight.size(1)
                m.weight.data.normal_(0, 0.01)
                m.bias.data.zero_()

        if use_pretrained == True:
            assert os.path.exists(pretrained), "{} does not exist".format(pretrained)
            pretrained_state_dict = torch.load(pretrained)
            logger.info('==> NOTE: loading mobilenet_v2 pretrained model {}'.format(pretrained))
            self.load_state_dict(pretrained_state_dict, strict=False)
        else: 
            logger.info('=> no mobilenet_v2 imagenet pretrained model! please download in https://drive.google.com/open?id=1jlto6HRVD3ipNkAl1lNhDbkBp7HylaqR')
    



def BackBone_MobileNet(config, is_train=True,**kwargs):
    
    mobilenet = MobileNetV2(frozen_mobilenet=config.model.frozen_mobilenet,   
                                feature_num=config.model.backbone_feature_num,**kwargs)

    if is_train and config.model.init_weights:
        mobilenet.init_weights(pretrained=config.model.backbone_pretrained_path)
    
    return  mobilenet
