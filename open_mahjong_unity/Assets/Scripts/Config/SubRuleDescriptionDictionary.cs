using System.Collections.Generic;

/// <summary>各子规则说明文案，供建房界面等使用。</summary>
public static class SubRuleDescriptionDictionary {
    public static readonly Dictionary<string, string> Descriptions = new Dictionary<string, string> {
        { "qingque/standard", "青雀是由莫莫柴编写的一款麻雀规则，旨在寻求一种在传统麻将行牌规则框架内的做大、抢和、兜牌防守三者平衡的麻雀游戏，同时试图为各类和牌提供基于美感和难度评估的赋分参照；如在测试中发现设计问题或有任何建议，可以联系规则制定人莫莫柴Q1107574，提交bug可在群906497522提交" },
        { "guobiao/standard", "国标麻将源于国家体育总局于1998年11月出台的《中国竞技麻将比赛规则(试行)》、是中国唯一由官方确立的竞技麻将规则；本平台参照Natsuki编著的新编MCR撰写运行逻辑，已通过所有牌例验证，如发现测试过程中出现了不符合国标麻将规则预期的行为，请向Q群906497522反馈。" },
        { "guobiao/xiaolin", "小林改版国标麻将，对国标麻将进行了番数平衡，还处于测试版，取消了8番起胡和底分，改为点和得分x2，自摸番三。非竞技规则，只为娱乐。" },
        { "guobiao/kshen", "K神改版国标麻将，新增镜同、四连刻等番种，复合番100封顶，默认8番起和。点和：12分以下三家各付n；12分以上两家各付12，放炮者付3n-12。自摸三家各付n。可开启错和、可自定义起和番。出现计分bug可在群里向q975653345反馈" },
        { "guobiao/lanshi", "蓝十改版的国标麻将规则，对国标麻将的番种表进行了全面的修改，并根据番种的难度调整了评分，5分起和，授受制为半全铳半分付。如在测试中发现设计问题或有任何建议，可以联系规则制定人蓝十QQ1002094810。" },
        { "classical/standard", "本规则为根据《绘图麻雀牌谱》《想定宁波规则》等书籍文献资料汇总而成的，试图还原1920年代左右或以前的早期麻将样貌的麻将规则。相比现代规则，古典麻雀有番种体系简单、重刻杠幺九、未和牌家计分等特点，具有独特风味。" },
        { "sichuan/standard", "四川麻将（血战到底）内测中......想赤石的可以来逛逛工地" },
        { "changsha/classic_double_bird", "长沙麻将经典双鸟规则：108张数牌，可吃上家牌，258将小胡，大胡可叠加，和牌后翻两只鸟并按座位中鸟加倍。" },
        { "riichi/standard", "立直麻将参照天凤/雀魂规则进行设计，无双倍役满" },
        { "riichi/langyong", "让每一局，都像海浪般汹涌滔滔｜一、每吃、碰、杠一次，自己的浪涌点数+1（初始为0）。｜二、每1点浪涌，结算时输赢倍数+1。｜三、当全场浪涌累计达到4点，进入“浪潮模式”，结算时倍数再+1。｜四、规则内置可食替｜规则提供：b站up大理石狐自恧" },
    };

    static SubRuleDescriptionDictionary() {
        Descriptions["new_rule/standard"] = "\u65b0\u89c4\u5219\u6d4b\u8bd5\u7248\uff1a\u56fd\u6807/\u9752\u96c0\u5f0f\u5b57\u724c\u9ebb\u5c06\u6846\u67b6\uff0c\u91c7\u7528\u8840\u6218\u5230\u5e95\u6d41\u7a0b\uff1b\u4e00\u4eba\u548c\u724c\u540e\u672c\u5c40\u7ee7\u7eed\uff0c\u76f4\u5230\u4e09\u5bb6\u548c\u724c\u6216\u724c\u5c71\u6478\u5b8c\u3002\u65e0\u82b1\u724c\u3001\u65e0\u5b9a\u7f3a\u3001\u65e0\u67e5\u53eb\u3001\u65e0\u8d77\u548c\u9650\u5236\uff0c\u7ed3\u7b97\u4e3a\u8d62\u5bb6\u83b7\u5f97\u756a\u6570\u7684\u516d\u500d\u70b9\u6570\u3002";
    }

    public static string GetDescription(string subRule) {
        return subRule != null && Descriptions.TryGetValue(subRule, out string desc) ? desc : "";
    }
}
